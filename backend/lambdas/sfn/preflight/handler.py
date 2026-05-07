"""
Preflight Lambda — extract zip, classify files, copy non-IaC assets straight to output.

Returns:
  fileList        — IaC source files uploaded to staging/in/
  preservedFiles  — non-IaC files (zips, scripts) copied to staging/out/ unchanged
  directoryTree   — {directory: [filename, ...]} map for the planning step
  stagingPrefix   — S3 prefix for staging/in files
  fileCount / skippedCount
"""
import io
import os
import zipfile

import boto3
from botocore.config import Config

from ddb_utils import update_job_step

s3  = boto3.client("s3", config=Config(signature_version="s3v4"))
ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]

MAX_FILES          = 200
MAX_FILE_BYTES     = 1_048_576       # 1 MB per file
MAX_ZIP_BYTES      = 50 * 1_048_576  # 50 MB total
FILE_SUMMARY_CHARS = 300             # chars of each IaC file sent to planner

# Extensions treated as IaC / translatable source code
IaC_EXTENSIONS = frozenset({
    ".tf", ".tfvars", ".hcl",           # Terraform
    ".json", ".yaml", ".yml",            # CloudFormation / SAM / CDK JSON
    ".py",                               # CDK Python
    ".ts",                               # CDK TypeScript
    ".java",                             # CDK Java
    ".cs",                               # CDK C#
    ".go",                               # CDK Go
})

# Extensions treated as preserved assets (copy to output unchanged)
PRESERVED_EXTENSIONS = frozenset({
    ".zip",   # Lambda function code
    ".sh",    # Shell scripts referenced in IaC
    ".ps1",   # PowerShell scripts
})

# Extensions we always skip
SKIP_EXTENSIONS = frozenset({
    ".lock", ".hcl",           # .terraform.lock.hcl — provider lock files
    ".tfstate", ".backup",     # state files
    ".log",
})

# Path fragments that indicate generated/cache directories to skip
SKIP_PATH_FRAGMENTS = frozenset({
    ".terraform/", "node_modules/", "__pycache__/", ".venv/",
    "cdk.out/", ".git/", "dist/",   # dist/ contains pre-built zips — we handle those separately
})


def should_skip_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return any(frag in p for frag in SKIP_PATH_FRAGMENTS)


# ── Source language detection ─────────────────────────────────────────────────

_LANG_LABELS = {
    "terraform":      "Terraform (.tf)",
    "cloudformation": "CloudFormation (YAML/JSON)",
    "sam":            "SAM (YAML/JSON)",
    "cdk":            "CDK (TypeScript/Python/Java/C#/Go)",
}


def detect_source_language(iac_files: list, file_summaries: dict) -> str | None:
    """
    Infer the most likely source language from file extensions and content.
    Returns one of: 'terraform', 'cloudformation', 'sam', 'cdk', or None (uncertain).
    """
    ext_counts: dict[str, int] = {}
    for f in iac_files:
        ext_counts[f["ext"]] = ext_counts.get(f["ext"], 0) + 1
        # cdk.json is a definitive CDK signal
        if os.path.basename(f["path"]) == "cdk.json":
            return "cdk"

    # .tf files → Terraform (most unambiguous signal)
    if ext_counts.get(".tf", 0) > 0:
        return "terraform"

    # YAML/JSON → inspect content for SAM vs CloudFormation
    yaml_json_exts = {".yaml", ".yml", ".json"}
    yaml_files = [f for f in iac_files if f["ext"] in yaml_json_exts]
    sam_hits, cfn_hits = 0, 0
    for f in yaml_files:
        content = file_summaries.get(f["path"], "")
        if "AWS::Serverless" in content or ("Transform" in content and "Serverless" in content):
            sam_hits += 1
        elif "AWSTemplateFormatVersion" in content or ("Resources" in content and "Type: AWS::" in content):
            cfn_hits += 1
    if sam_hits > 0:
        return "sam"
    if cfn_hits > 0:
        return "cloudformation"

    # Code-only files → CDK
    cdk_exts = {".ts", ".py", ".java", ".cs", ".go"}
    if any(ext_counts.get(e, 0) > 0 for e in cdk_exts):
        # Only declare CDK if there are no YAML/JSON files that look like raw templates
        if not yaml_files:
            return "cdk"

    return None  # uncertain — don't block


def validate_source_language(declared: str, detected: str | None) -> None:
    """
    Raise a ValueError if the detected language clearly doesn't match
    what the user declared. Passes through when detection is uncertain (None).
    """
    if detected is None or detected == declared:
        return

    # CDK is declared but files look like Terraform/CFN/SAM → mismatch
    # Terraform is declared but files look like SAM → mismatch
    # etc.
    detected_label  = _LANG_LABELS.get(detected,  detected)
    declared_label  = _LANG_LABELS.get(declared,  declared)
    raise ValueError(
        f"LANGUAGE_MISMATCH: The uploaded files look like {detected_label}, "
        f"but you selected {declared_label} as the source language. "
        f"Please start a new translation with the correct source format."
    )


def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "PREFLIGHT")

    user_id   = event["userId"]
    job_id    = event["jobId"]
    bucket    = event["artifactsBucket"]
    input_key = event["inputS3Key"]

    obj = s3.get_object(Bucket=bucket, Key=input_key)
    zip_bytes = obj["Body"].read()

    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise ValueError(f"Zip exceeds {MAX_ZIP_BYTES // (1024*1024)} MB limit")

    staging_in  = f"staging/{user_id}/{job_id}/in"
    staging_out = f"staging/{user_id}/{job_id}/out"

    iac_files:       list[dict] = []
    preserved_files: list[dict] = []
    skipped:         list[dict] = []
    directory_tree:  dict[str, list[str]] = {}   # dir → [filename, ...]
    file_summaries:  dict[str, str] = {}         # relative path → first N chars

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            raw_path = info.filename.lstrip("/").replace("\\", "/")
            if should_skip_path(raw_path):
                continue

            basename = os.path.basename(raw_path)
            ext      = os.path.splitext(basename)[1].lower()
            dirname  = os.path.dirname(raw_path) or "."

            # ── Skip size-exceeded files ──────────────────────────────────────
            if info.file_size > MAX_FILE_BYTES:
                skipped.append({"path": raw_path, "reason": "too_large"})
                continue

            # ── Skip explicitly ignored extensions ───────────────────────────
            if ext in SKIP_EXTENSIONS or basename.startswith("."):
                continue

            body = zf.read(info.filename)

            # ── Preserved assets (zips etc.) — copy straight to output ────────
            if ext in PRESERVED_EXTENSIONS:
                out_key = f"{staging_out}/{raw_path}"
                s3.put_object(Bucket=bucket, Key=out_key, Body=body)
                preserved_files.append({
                    "path":   raw_path,
                    "outKey": out_key,
                    "size":   info.file_size,
                    "ext":    ext,
                })
                # Also put in staging/in so translate can reference it
                in_key = f"{staging_in}/{raw_path}"
                s3.put_object(Bucket=bucket, Key=in_key, Body=body)
                # Add to directory tree so planner sees it
                directory_tree.setdefault(dirname, []).append(basename)
                continue

            # ── IaC files ─────────────────────────────────────────────────────
            if ext in IaC_EXTENSIONS:
                if len(iac_files) >= MAX_FILES:
                    skipped.append({"path": raw_path, "reason": "file_limit_reached"})
                    continue

                in_key = f"{staging_in}/{raw_path}"
                s3.put_object(Bucket=bucket, Key=in_key, Body=body)

                iac_files.append({
                    "path":   raw_path,
                    "s3Key":  in_key,
                    "size":   info.file_size,
                    "ext":    ext,
                })

                # Store a short content summary for the planner (avoids passing full contents)
                try:
                    text = body.decode("utf-8", errors="replace")
                    file_summaries[raw_path] = text[:FILE_SUMMARY_CHARS]
                except Exception:
                    file_summaries[raw_path] = ""

                directory_tree.setdefault(dirname, []).append(basename)
                continue

            # ── Everything else: skip ─────────────────────────────────────────
            skipped.append({"path": raw_path, "reason": "not_iac"})

    if not iac_files:
        raise ValueError("No valid IaC files found in the archive")

    # Detect the actual source language and fail fast if it clearly doesn't
    # match what the user declared — before any Bedrock calls are made.
    declared_lang = event.get("sourceLang", "")
    detected_lang = detect_source_language(iac_files, file_summaries)
    validate_source_language(declared_lang, detected_lang)

    # Persist skipped list to DDB for user visibility
    if skipped:
        ddb.Table(JOBS_TABLE).update_item(
            Key={"userId": user_id, "jobId": job_id},
            UpdateExpression="SET skippedFiles = :s",
            ExpressionAttributeValues={":s": skipped},
        )

    return {
        "fileList":       iac_files,
        "preservedFiles": preserved_files,
        "fileSummaries":  file_summaries,
        "directoryTree":  directory_tree,
        "stagingPrefix":  staging_in,
        "fileCount":      len(iac_files),
        "skippedCount":   len(skipped),
        "preservedCount": len(preserved_files),
    }
