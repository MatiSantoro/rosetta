"""
TranslateUnit Lambda - translate ONE unit (directory/module/stack) to the target language.
Accepts all source files for the unit, returns multiple output files as JSON.
"""
import json
import os

import boto3
from botocore.config import Config

from ddb_utils import update_job_step, add_job_tokens
from bedrock_utils import bedrock_tool_call
from toon_utils import toon_symbol_table

s3      = boto3.client("s3", config=Config(signature_version="s3v4"))
ddb     = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE         = os.environ["JOBS_TABLE"]
TRANSLATE_MODEL_ID = os.environ.get("TRANSLATE_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
OPUS_MODEL_ID      = os.environ.get("OPUS_MODEL_ID",      "us.anthropic.claude-opus-4-6-v1")
MAX_FILE_CHARS     = 8000

LANG_LABELS = {
    "terraform":      "Terraform (HCL)",
    "cloudformation": "AWS CloudFormation (YAML)",
    "sam":            "AWS SAM (YAML)",
    "cdk_typescript": "AWS CDK (TypeScript)",
    "cdk_python":     "AWS CDK (Python)",
    "cdk_java":       "AWS CDK (Java)",
    "cdk_csharp":     "AWS CDK (C#)",
    "cdk_go":         "AWS CDK (Go)",
}

def lang_key(lang, cdk_lang=None):
    return f"cdk_{cdk_lang}" if lang == "cdk" and cdk_lang else lang

# ── System prompt: base rules always sent; target rules only when relevant ────
# Splitting saves 200–400 tokens per call by excluding irrelevant sections.
# The combined (base + target) prompt is cached — parallel units and retries
# within the same job share the same target, so they all get cache hits.

_SYSTEM_BASE = """\
You are an expert AWS infrastructure engineer specialising in IaC translation.

You will receive one or more source files from a single directory/module and must
translate them as a UNIT into the target language.

GENERAL RULES:
1. Produce ALL files listed in expected_output_files.
2. Every CloudFormation/SAM template MUST have a Resources section.
3. Terraform output: split into main.tf + variables.tf + outputs.tf.
   Root modules also get providers.tf and backend.tf; child modules do not.
4. CDK output: one class file per Stack (root) or Construct (module).
5. Preserve Lambda zip file references — never translate zip files.
6. Only declare data sources actually used in output.
7. Convert identifiers: snake_case (Terraform), PascalCase (CloudFormation), camelCase (CDK).
8. Symbol table identifiers: reference them, do not redefine.
9. Do NOT add hardening not present in source."""

_TARGET_RULES = {
    "terraform": """
TARGET-SPECIFIC RULES — TERRAFORM:
- Use aws_iam_role_policy_attachment (never managed_policy_arns on the role resource).
- Lambda without code: filename = "placeholder.zip" + lifecycle { ignore_changes = [filename] }.
- Lambda WITH zip ref: use the relative path provided in lambdaZipRefs.
- snake_case resource names, never repeat the resource type in the name.""",

    "cloudformation": """
TARGET-SPECIFIC RULES — CLOUDFORMATION:
- Merge ALL directory files into ONE template file.
- variables.tf → Parameters section; outputs.tf → Outputs section (same file as Resources).
- Use !Ref, !GetAtt, !Sub for cross-resource references.
- Stateful resources: add DeletionPolicy: Retain and UpdateReplacePolicy: Retain.""",

    "sam": """
TARGET-SPECIFIC RULES — SAM:
- Merge ALL directory files into ONE template file with Transform: AWS::Serverless-2016-10-31.
- variables.tf → Parameters section; outputs.tf → Outputs section.
- Use AWS::Serverless::* resource types for Lambda, API, DynamoDB where available.
- Stateful resources: add DeletionPolicy: Retain and UpdateReplacePolicy: Retain.""",

    "cdk": """
TARGET-SPECIFIC RULES — CDK:
- Import from aws-cdk-lib only (never @aws-cdk/* scoped packages).
- Prefer L2 constructs; fall back to L1 (Cfn*) only when no L2 exists.
- Use typed enums (e.g. s3.BucketEncryption.S3_MANAGED) not raw strings.
- Lambda with zip: Code.fromAsset("path/to/lambda.zip").
- Use grant methods (grantRead, grantReadWrite) instead of manual IAM policies.""",
}


def build_system_prompt(target_lang: str) -> str:
    """Return base rules + the single relevant target-language section."""
    target_rules = _TARGET_RULES.get(target_lang, "")
    return _SYSTEM_BASE + target_rules


def handler(event, context):
    user_id  = event["userId"]
    job_id   = event["jobId"]
    unit     = event["unit"]
    bucket   = event["artifactsBucket"]
    use_opus = event.get("useOpus", False)

    update_job_step(ddb, JOBS_TABLE, user_id, job_id, "TRANSLATE")

    source_lang = event.get("sourceLang", "")
    target_lang = event.get("targetLang", "")
    src_label   = LANG_LABELS.get(lang_key(source_lang, event.get("sourceCdkLang")), source_lang)
    tgt_label   = LANG_LABELS.get(lang_key(target_lang, event.get("targetCdkLang")), target_lang)

    dep_graph    = event.get("depGraph") or {}
    retry_errors = []
    if event.get("validateResult") and not event["validateResult"].get("ok"):
        retry_errors = [e.get("msg", str(e)) for e in event["validateResult"].get("errors", [])]

    src_dir      = unit.get("sourceDirectory", ".")
    unit_id      = unit.get("unitId", src_dir)
    source_files = unit.get("sourceFiles", [])
    output_dir   = unit.get("outputDirectory", src_dir)
    output_files = unit.get("outputFiles", [])
    staging_in   = f"staging/{user_id}/{job_id}/in"

    file_blocks = []
    for fname in source_files:
        rel_path = f"{src_dir}/{fname}" if src_dir != "." else fname
        s3_key   = f"{staging_in}/{rel_path}"
        try:
            body = s3.get_object(Bucket=bucket, Key=s3_key)["Body"].read().decode("utf-8", errors="replace")
            file_blocks.append(f"=== {rel_path} ===\n{body[:MAX_FILE_CHARS]}")
        except Exception:
            file_blocks.append(f"=== {rel_path} === [could not load]")

    expected_str = "\n".join(f"  - {output_dir}/{f['name']} (role: {f['role']})" for f in output_files)

    sym_section = ""
    if dep_graph.get("symbolTable"):
        # TOON encoding saves ~40% tokens vs JSON on the symbol table
        sym_section = "\n\nSymbol table — OTHER units (reference, do not redefine):\n" + toon_symbol_table(dep_graph["symbolTable"])[:2000]

    zip_refs = unit.get("lambdaZipRefs", [])
    zip_section = ""
    if zip_refs:
        zip_section = "\n\nLambda zip files (use relative path, do not translate):\n" + "\n".join(f"  {z}" for z in zip_refs)

    error_section = ""
    if retry_errors:
        error_section = "\n\nPrevious validation errors to fix:\n" + "\n".join(f"  - {e}" for e in retry_errors)

    user_msg = (
        f"Translate from {src_label} to {tgt_label}.\n\n"
        f"Unit: {unit_id}\n"
        f"Description: {unit.get('description', '')}\n"
        f"Strategy: {unit.get('strategy', '')}\n\n"
        f"SOURCE FILES:\n{chr(10).join(file_blocks) or '(none)'}\n\n"
        f"EXPECTED OUTPUT FILES:\n{expected_str or '(determine from source)'}"
        f"{sym_section}{zip_section}{error_section}\n\n"
        "Return the JSON with all output files."
    )

    translate_schema = {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "path":    {"type": "string", "description": "Relative output path, e.g. 'modules/storage/main.tf'"},
                        "content": {"type": "string", "description": "Full file content"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        "required": ["files"],
    }

    model_id      = OPUS_MODEL_ID if use_opus else TRANSLATE_MODEL_ID
    system_prompt = build_system_prompt(target_lang)

    response, result = bedrock_tool_call(
        bedrock,
        tool_name="submit_translated_files",
        tool_description="Submit all translated output files for this translation unit.",
        output_schema=translate_schema,
        use_cache=True,   # caches system prompt + tool schema across parallel units
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        inferenceConfig={"maxTokens": 16000},
    )

    tokens_in  = response["usage"]["inputTokens"]
    tokens_out = response["usage"]["outputTokens"]
    files      = result.get("files", [])

    if not files:
        raise ValueError(f"Translate returned no files for unit {unit_id}")

    staging_out         = f"staging/{user_id}/{job_id}/out"
    output_file_records = []

    for file_obj in files:
        rel_path = file_obj.get("path", "").lstrip("/")
        content  = file_obj.get("content", "")
        if not rel_path or not content:
            continue
        out_key = f"{staging_out}/{rel_path}"
        body    = content.encode("utf-8")
        s3.put_object(Bucket=bucket, Key=out_key, Body=body)
        output_file_records.append({"path": rel_path, "outKey": out_key, "size": len(body)})

    add_job_tokens(ddb, JOBS_TABLE, user_id, job_id, tokens_in, tokens_out)

    return {
        "unitId":      unit_id,
        "outputFiles": output_file_records,
        "tokensIn":    tokens_in,
        "tokensOut":   tokens_out,
    }
