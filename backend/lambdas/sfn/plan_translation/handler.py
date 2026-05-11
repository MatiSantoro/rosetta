"""
PlanTranslation Lambda — analyse the full project structure and produce a
translation plan that groups source files into translation units.

Each unit is a self-contained deployment artifact in the target language:
  - Terraform module dir (main.tf + variables.tf + outputs.tf + ...)
  - CloudFormation/SAM template (single .yaml)
  - CDK Stack (one class per Stack)

The LLM also builds a project-wide symbol table used by TranslateUnit
for cross-unit reference resolution.

Returns:
  units        — list of translation units
  symbolTable  — project-wide identifiers
  planNotes    — LLM reasoning about the translation approach
"""
import os

import boto3
from botocore.config import Config

from ddb_utils import update_job_step
from bedrock_utils import bedrock_tool_call
from toon_utils import toon_file_inventory, toon_table

ddb     = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE        = os.environ["JOBS_TABLE"]
TRANSLATE_MODEL   = os.environ.get("TRANSLATE_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
MAX_SUMMARY_FILES = 40   # cap how many file summaries we send to keep prompt size reasonable

LANG_LABELS = {
    "terraform":      "Terraform (HCL)",
    "cloudformation": "AWS CloudFormation (YAML)",
    "sam":            "AWS SAM (YAML)",
    "cdk":            "AWS CDK",
}

SYSTEM_PROMPT = """\
You are an expert infrastructure engineer and IaC architect. Your task is to analyse
a project's file structure and produce a precise JSON translation plan.

A translation unit is the minimal set of source files that map to a single deployable
artifact in the target language:
- Terraform module (all .tf files in the same directory)
- CloudFormation / SAM template (a single .yaml file)
- CDK Stack class (a single class/file)

Rules you MUST follow:
1. Every directory that contains IaC source files is a separate unit.
2. Variables/outputs files belong to the SAME unit as the resources in that directory — never split them.
3. Zip files and non-IaC assets belong to the unit whose directory they live in; they are preserved unchanged.
4. When translating TO Terraform: produce main.tf + variables.tf + outputs.tf per unit (+ providers.tf and backend.tf for root).
5. When translating TO CloudFormation/SAM: produce one .yaml per unit; if a unit has >30 resources suggest nested stacks, otherwise inline.
6. When translating TO CDK: produce one Stack class for the root, one Construct per module.
7. The root unit (directory ".") always exists.
8. Identify Lambda zip files and note which resource uses them.

Return ONLY valid JSON — no markdown, no explanation outside the JSON structure."""

UNIT_SCHEMA = """\
{
  "units": [
    {
      "unitId": "string — unique identifier, use the directory path (e.g. '.' or 'modules/storage')",
      "description": "string — one sentence describing what this unit does",
      "sourceDirectory": "string — directory path relative to zip root",
      "sourceFiles": ["list of filenames in this directory that are IaC files"],
      "outputDirectory": "string — where output files should be placed",
      "outputFiles": [
        {
          "name": "string — output filename",
          "role": "string — one of: resources|variables|outputs|providers|backend|root_template|nested_template|stack_class|construct_class"
        }
      ],
      "strategy": "string — one of: single_template|nested_stack|tf_root_module|tf_module|cdk_stack|cdk_construct",
      "lambdaZipRefs": ["list of zip file paths used by Lambda resources in this unit"],
      "dependsOn": ["list of unitIds this unit references"]
    }
  ],
  "symbolTable": {
    "variables": {"name": "type (file)"},
    "resources":  {"name": "resource_type (file)"},
    "outputs":    {"name": "value_expression (file)"},
    "modules":    {"name": "source_path (file)"}
  },
  "planNotes": "string — key observations about the project and translation approach"
}"""


def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "PLAN")

    source_lang = event.get("sourceLang", "")
    target_lang = event.get("targetLang", "")
    cdk_lang    = event.get("sourceCdkLang") or event.get("targetCdkLang")

    preflight   = event.get("preflightResult", {})
    directory_tree  = preflight.get("directoryTree", {})
    file_list       = preflight.get("fileList", [])
    preserved_files = preflight.get("preservedFiles", [])
    file_summaries  = preflight.get("fileSummaries", {})

    src_label = LANG_LABELS.get(source_lang, source_lang)
    tgt_label = LANG_LABELS.get(target_lang, target_lang)
    if target_lang == "cdk" and cdk_lang:
        tgt_label = f"AWS CDK ({cdk_lang})"
    if source_lang == "cdk" and cdk_lang:
        src_label = f"AWS CDK ({cdk_lang})"

    # ── Build project overview for the prompt (TOON for tabular data) ──────────

    # File inventory as TOON tabular array — ~40-50% fewer tokens than JSON/text
    file_inventory_toon = toon_file_inventory(file_list, directory_tree)

    # Preserved assets as TOON table (flat and uniform)
    preserved_toon = "(none)"
    if preserved_files:
        preserved_toon = toon_table(
            "preserved_assets",
            [{"path": p["path"], "size": p["size"]} for p in preserved_files],
            ["path", "size"],
        )

    # File content previews — keep as plain text (code content, not tabular)
    summary_lines = []
    shown = 0
    for rel_path, summary in file_summaries.items():
        if shown >= MAX_SUMMARY_FILES:
            summary_lines.append(f"  ... ({len(file_summaries) - shown} more files not shown)")
            break
        if summary.strip():
            truncated = summary[:200].replace("\n", " ").strip()
            summary_lines.append(f"  {rel_path}: {truncated}")
            shown += 1

    user_msg = f"""\
Translate this project from {src_label} to {tgt_label}.

## IaC file inventory (TOON format — path, directory, size in bytes)
{file_inventory_toon}

## Non-IaC assets (preserved unchanged, TOON format)
{preserved_toon}

## File content previews (first 200 chars each)
{chr(10).join(summary_lines) or "  none"}

## Total: {len(file_list)} IaC files, {len(preserved_files)} preserved assets

Produce the translation plan JSON following this exact schema:
{UNIT_SCHEMA}"""

    output_file_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string", "enum": ["resources", "variables", "outputs", "providers", "backend", "root_template", "nested_template", "stack_class", "construct_class"]},
        },
        "required": ["name", "role"],
    }
    unit_schema = {
        "type": "object",
        "properties": {
            "unitId":          {"type": "string"},
            "description":     {"type": "string"},
            "sourceDirectory": {"type": "string"},
            "sourceFiles":     {"type": "array", "items": {"type": "string"}},
            "outputDirectory": {"type": "string"},
            "outputFiles":     {"type": "array", "items": output_file_schema},
            "strategy":        {"type": "string", "enum": ["single_template", "nested_stack", "tf_root_module", "tf_module", "cdk_stack", "cdk_construct"]},
            "lambdaZipRefs":   {"type": "array", "items": {"type": "string"}},
            "dependsOn":       {"type": "array", "items": {"type": "string"}},
        },
        "required": ["unitId", "sourceDirectory", "sourceFiles", "outputDirectory", "outputFiles", "strategy"],
    }
    plan_schema = {
        "type": "object",
        "properties": {
            "units": {"type": "array", "items": unit_schema, "minItems": 1},
            "symbolTable": {
                "type": "object",
                "properties": {
                    "variables": {"type": "object"},
                    "resources":  {"type": "object"},
                    "outputs":    {"type": "object"},
                    "modules":    {"type": "object"},
                },
            },
            "planNotes": {"type": "string"},
        },
        "required": ["units", "symbolTable", "planNotes"],
    }

    response, plan = bedrock_tool_call(
        bedrock,
        tool_name="submit_translation_plan",
        tool_description="Submit the structured translation plan for this IaC project.",
        output_schema=plan_schema,
        modelId=TRANSLATE_MODEL,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        inferenceConfig={"maxTokens": 8192},
    )

    if not plan.get("units"):
        raise ValueError("PlanTranslation returned empty units list")

    return {
        "units":       plan["units"],
        "symbolTable": plan.get("symbolTable", {}),
        "planNotes":   plan.get("planNotes", ""),
        "tokensIn":    response["usage"]["inputTokens"],
        "tokensOut":   response["usage"]["outputTokens"],
    }
