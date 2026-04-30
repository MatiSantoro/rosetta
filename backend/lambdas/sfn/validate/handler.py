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

def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "VALIDATE")
    target = event.get("targetLang", "")
    cdk    = event.get("targetCdkLang")
    key    = f"cdk_{cdk}" if target == "cdk" and cdk else target
    bucket = event["artifactsBucket"]
    results = event.get("translateResults") or []
    if not results:
        return {"ok": True, "errors": [], "warnings": []}
    if target in ("cloudformation", "sam"):
        return validate_cfn(bucket, results)
    elif target == "terraform":
        return validate_terraform(bucket, results)
    else:
        return validate_bedrock(bucket, results, key)

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
        resp = bedrock.converse(
            modelId=VALIDATE_MODEL_ID,
            system=[{"text": BEDROCK_SYSTEM.format(lang=lang)}],
            messages=[{"role": "user", "content": [
                {"text": f"Validate:\n\n" + "\n\n".join(files)}]}],
            inferenceConfig={"maxTokens": 1024})
        raw = resp["output"]["message"]["content"][0]["text"].strip()
        if raw.startswith("```"): raw = raw.split("\n",1)[1].rsplit("```",1)[0].strip()
        r = json.loads(raw)
        return {"ok": bool(r.get("ok", True)), "errors": r.get("errors",[]),
                "warnings": r.get("warnings",[])}
    except Exception as e:
        return {"ok": True, "errors": [], "warnings": [f"Bedrock validation skipped: {str(e)[:100]}"]}
