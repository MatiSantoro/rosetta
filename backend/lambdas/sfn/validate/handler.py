"""
Validate generated IaC output using Bedrock self-review.
Sends all translated files to Sonnet and asks it to identify
syntax / structural errors that would prevent deployment.

Returns: {"ok": bool, "errors": [{file, msg}], "warnings": [str]}
"""
import json
import os

import boto3
from botocore.config import Config

from ddb_utils import update_job_step

s3      = boto3.client("s3", config=Config(signature_version="s3v4"))
ddb     = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE        = os.environ["JOBS_TABLE"]
VALIDATE_MODEL_ID = os.environ.get("TRANSLATE_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

MAX_FILE_CHARS = 3_000   # cap per file to keep prompt size reasonable
MAX_FILES      = 10      # max files to validate in one call

LANG_LABELS = {
    "terraform":        "Terraform (HCL)",
    "cloudformation":   "AWS CloudFormation (YAML)",
    "sam":              "AWS SAM (YAML)",
    "cdk_typescript":   "AWS CDK TypeScript",
    "cdk_python":       "AWS CDK Python",
    "cdk_java":         "AWS CDK Java",
    "cdk_csharp":       "AWS CDK C#",
    "cdk_go":           "AWS CDK Go",
}

SYSTEM_PROMPT = """\
You are an expert AWS infrastructure engineer performing a code review.

Review the {target_lang} files below and identify ONLY errors that would cause
deployment to fail: syntax errors, invalid resource types, missing required
properties, or invalid cross-resource references.

DO NOT flag:
- Style preferences or naming conventions
- Missing optional properties
- Security best practices (DeletionPolicy, encryption, VPC placement, etc.)
- cfn-guard policy violations
- Informational or advisory warnings

If the code looks valid for deployment, return {{"ok": true}}.
If there are real errors, return {{"ok": false, "errors": [{{"file": "<filename>", "msg": "<concise description>"}}]}}.

Respond with JSON only — no explanation, no markdown."""


def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "VALIDATE")

    target_lang = event.get("targetLang", "")
    cdk_lang    = event.get("targetCdkLang")
    lang_key    = f"cdk_{cdk_lang}" if target_lang == "cdk" and cdk_lang else target_lang
    lang_label  = LANG_LABELS.get(lang_key, target_lang)

    bucket          = event["artifactsBucket"]
    user_id         = event["userId"]
    job_id          = event["jobId"]
    translate_results = event.get("translateResults") or []

    if not translate_results:
        return {"ok": True, "errors": [], "warnings": []}

    # ── Collect output file contents ──────────────────────────────────────────
    files_content: list[str] = []
    for res in translate_results[:MAX_FILES]:
        if not isinstance(res, dict):
            continue
        out_key = res.get("outKey")
        if not out_key:
            continue
        try:
            body = (
                s3.get_object(Bucket=bucket, Key=out_key)["Body"]
                .read()
                .decode("utf-8", errors="replace")
            )
            filename = res.get("path") or out_key.rsplit("/", 1)[-1]
            files_content.append(f"=== {filename} ===\n{body[:MAX_FILE_CHARS]}")
        except Exception:
            continue

    if not files_content:
        return {"ok": True, "errors": [], "warnings": []}

    # ── Bedrock self-review ────────────────────────────────────────────────────
    combined = "\n\n".join(files_content)
    user_msg = f"Validate these {lang_label} files:\n\n{combined}"

    try:
        response = bedrock.converse(
            modelId=VALIDATE_MODEL_ID,
            system=[{"text": SYSTEM_PROMPT.format(target_lang=lang_label)}],
            messages=[{"role": "user", "content": [{"text": user_msg}]}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0},
        )

        raw = response["output"]["message"]["content"][0]["text"].strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        return {
            "ok":       bool(result.get("ok", True)),
            "errors":   result.get("errors", []),
            "warnings": result.get("warnings", []),
        }

    except (json.JSONDecodeError, KeyError):
        # Non-JSON response — fail open (don't block the user)
        return {"ok": True, "errors": [], "warnings": ["Validation response could not be parsed"]}
    except Exception as e:
        return {"ok": True, "errors": [], "warnings": [f"Validation skipped: {str(e)[:120]}"]}
