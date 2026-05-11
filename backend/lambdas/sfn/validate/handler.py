"""
Validate generated IaC output using native tools + Bedrock self-review.

  CloudFormation / SAM  -> cfn-lint (pip layer)
  Terraform             -> terraform fmt -check (binary layer)
  CDK                   -> Bedrock self-review (no binary tool available)
"""
import json, os, subprocess, tempfile
import boto3
from botocore.config import Config
from ddb_utils import update_job_step
from bedrock_utils import bedrock_tool_call

s3      = boto3.client("s3", config=Config(signature_version="s3v4"))
ddb     = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE        = os.environ["JOBS_TABLE"]
VALIDATE_MODEL_ID = os.environ.get("TRANSLATE_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
TERRAFORM_BIN     = "/opt/bin/terraform"
MAX_FILE_CHARS    = 3000
MAX_FILES         = 10

LANG_LABELS = {
    "terraform": "Terraform (HCL)", "cloudformation": "AWS CloudFormation",
    "sam": "AWS SAM", "cdk_typescript": "CDK TypeScript",
    "cdk_python": "CDK Python", "cdk_java": "CDK Java",
    "cdk_csharp": "CDK C#", "cdk_go": "CDK Go",
}

BEDROCK_SYSTEM = """You are an expert AWS infrastructure engineer.
Review the {lang} files and identify ONLY errors that would cause deployment failure.
Do NOT flag style, optional properties, or security best practices.
Return JSON only: {{"ok": true}} or {{"ok": false, "errors": [{{"file": "f", "msg": "m"}}]}}"""

def _compute_units_to_retry(errors: list, raw_results: list, plan_units: list) -> list:
    """
    Given validation errors, return only the translation units that had failures.
    Units with no errors are already correct and don't need re-translation.

    Matching: error["file"] is the relative output path (e.g. "modules/storage/main.tf").
    We look that path up in each unit's outputFiles list to find the owning unitId.
    """
    if not errors:
        return []

    # Build file_path → unitId index from translate results
    file_to_unit: dict = {}
    for item in raw_results:
        if isinstance(item, dict) and "outputFiles" in item:
            uid = item.get("unitId", "")
            for f in item["outputFiles"]:
                file_to_unit[f.get("path", "")] = uid

    # Collect failed unit IDs
    failed_ids: set = set()
    for error in errors:
        err_file = error.get("file", "")
        uid = file_to_unit.get(err_file)
        if uid:
            failed_ids.add(uid)
        else:
            # Fuzzy match: error file may be a basename or partial path
            for path, uid in file_to_unit.items():
                if err_file and (err_file in path or path.endswith(err_file)):
                    failed_ids.add(uid)
                    break

    if not failed_ids:
        # Could not map errors to units — retry everything to be safe
        return plan_units

    return [u for u in plan_units if u.get("unitId", "") in failed_ids]


def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "VALIDATE")
    target     = event.get("targetLang", "")
    cdk        = event.get("targetCdkLang")
    key        = f"cdk_{cdk}" if target == "cdk" and cdk else target
    bucket     = event["artifactsBucket"]
    plan_units = event.get("planResult", {}).get("units", [])
    raw_results = event.get("translateResults") or []

    if not raw_results:
        return {"ok": True, "errors": [], "warnings": [], "unitsToRetry": []}

    # Flatten unit results → list of {path, outKey} for validators
    flat_results = []
    for item in raw_results:
        if isinstance(item, dict):
            if "outputFiles" in item:
                flat_results.extend(item["outputFiles"])
            elif "outKey" in item:
                flat_results.append(item)

    if not flat_results:
        return {"ok": True, "errors": [], "warnings": [], "unitsToRetry": []}

    if target in ("cloudformation", "sam"):
        result = validate_cfn(bucket, flat_results)
    elif target == "terraform":
        result = validate_terraform(bucket, flat_results)
    else:
        result = validate_bedrock(bucket, flat_results, key)

    # Attach the list of units that need re-translation (empty when ok=True)
    result["unitsToRetry"] = _compute_units_to_retry(
        result.get("errors", []), raw_results, plan_units
    )

    # Persist the validation report to the Jobs table for the frontend to surface
    user_id = event.get("userId")
    job_id  = event.get("jobId")
    if user_id and job_id:
        ddb.Table(JOBS_TABLE).update_item(
            Key={"userId": user_id, "jobId": job_id},
            UpdateExpression="SET validationReport = :r",
            ExpressionAttributeValues={":r": {
                "ok":       result["ok"],
                "errors":   result.get("errors", []),
                "warnings": result.get("warnings", []),
            }},
        )

    return result

def _download(bucket, res):
    out_key = res.get("outKey")
    if not out_key:
        return None, None
    body = s3.get_object(Bucket=bucket, Key=out_key)["Body"].read().decode("utf-8", errors="replace")
    filename = res.get("path") or out_key.rsplit("/", 1)[-1]
    return body, filename

def validate_cfn(bucket, results):
    errors, warnings = [], []
    for res in results:
        if not isinstance(res, dict): continue
        try:
            body, filename = _download(bucket, res)
            if body is None: continue
        except Exception as e:
            warnings.append(str(e)[:80]); continue
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(body); tmp = f.name
        try:
            proc = subprocess.run(
                ["python", "-m", "cfnlint", tmp, "--format", "json"],
                capture_output=True, text=True, timeout=60)
            if proc.stdout:
                for issue in json.loads(proc.stdout):
                    rule = issue.get("Rule", {}).get("Id", "")
                    if not rule.startswith(("I", "W")):
                        errors.append({"file": filename, "rule": rule,
                                       "msg": issue.get("Message", "cfn-lint error")})
        except FileNotFoundError:
            warnings.append("cfn-lint not available")
        except Exception as e:
            warnings.append(f"cfn-lint: {str(e)[:80]}")
        finally:
            try: os.unlink(tmp)
            except: pass
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}

def validate_terraform(bucket, results):
    """
    Run `terraform fmt` (auto-format) on each .tf file.
    - If the file is valid HCL: fmt fixes formatting in-place and we upload
      the corrected version back to S3. No error, no retry.
    - If the file is unparseable (real syntax error): fmt exits non-zero
      with a message on stderr. We report that as an error → triggers retry.
    This eliminates retries for cosmetic formatting issues while still
    catching genuine HCL syntax errors.
    """
    errors, warnings = [], []
    for res in results:
        if not isinstance(res, dict): continue
        out_key = res.get("outKey")
        try:
            body, filename = _download(bucket, res)
            if body is None: continue
        except Exception as e:
            warnings.append(str(e)[:80]); continue

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write(body); tmp = f.name

        try:
            # fmt without -check: auto-fixes formatting, exits non-zero only
            # on real parse errors (stderr will have the error detail)
            proc = subprocess.run(
                [TERRAFORM_BIN, "fmt", tmp],
                capture_output=True, text=True, timeout=15)

            if proc.returncode != 0:
                # Real HCL syntax error — report it so the retry loop fixes it
                msg = proc.stderr.strip() or "HCL syntax error — file could not be parsed"
                errors.append({"file": filename, "msg": msg})
            else:
                # fmt succeeded: read the auto-formatted content and write back to S3
                with open(tmp, "r") as fh:
                    formatted = fh.read()
                if formatted != body and out_key:
                    s3.put_object(Bucket=bucket, Key=out_key,
                                  Body=formatted.encode("utf-8"))

        except FileNotFoundError:
            warnings.append("terraform binary not available — skipping TF format check")
        except Exception as e:
            warnings.append(f"terraform fmt: {str(e)[:80]}")
        finally:
            try: os.unlink(tmp)
            except: pass

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}

def validate_bedrock(bucket, results, lang_key):
    lang = LANG_LABELS.get(lang_key, lang_key)
    files = []
    for res in results[:MAX_FILES]:
        if not isinstance(res, dict): continue
        try:
            body, filename = _download(bucket, res)
            if body: files.append(f"=== {filename} ===\n{body[:MAX_FILE_CHARS]}")
        except: pass
    if not files:
        return {"ok": True, "errors": [], "warnings": []}
    try:
        _, r = bedrock_tool_call(
            bedrock,
            tool_name="report_validation",
            tool_description="Report structural validation results for the generated IaC code.",
            output_schema={
                "type": "object",
                "properties": {
                    "ok":       {"type": "boolean", "description": "True if no blocking errors found"},
                    "errors":   {"type": "array",   "items": {"type": "object", "properties": {"file": {"type": "string"}, "msg": {"type": "string"}}, "required": ["file", "msg"]}},
                    "warnings": {"type": "array",   "items": {"type": "string"}},
                },
                "required": ["ok", "errors", "warnings"],
            },
            modelId=VALIDATE_MODEL_ID,
            system=[{"text": BEDROCK_SYSTEM.format(lang=lang)}],
            messages=[{"role": "user", "content": [{"text": "Validate:\n\n" + "\n\n".join(files)}]}],
            inferenceConfig={"maxTokens": 1024},
        )
        return {"ok": bool(r.get("ok", True)), "errors": r.get("errors", []), "warnings": r.get("warnings", [])}
    except Exception as e:
        return {"ok": True, "errors": [], "warnings": [f"Bedrock validation skipped: {str(e)[:100]}"]}
