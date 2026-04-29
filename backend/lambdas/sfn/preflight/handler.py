import io
import os
import zipfile

import boto3

from ddb_utils import update_job_step

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]
MAX_FILES = 200
MAX_FILE_BYTES = 1_048_576       # 1 MB per file
MAX_ZIP_BYTES = 50 * 1_048_576   # 50 MB total

IaC_EXTENSIONS = frozenset({
    ".tf", ".tfvars",           # Terraform / HCL
    ".hcl",
    ".json",                    # CloudFormation / CDK
    ".yaml", ".yml",            # CloudFormation / SAM
    ".py",                      # CDK Python
    ".ts",                      # CDK TypeScript
    ".java",                    # CDK Java
    ".cs",                      # CDK C#
    ".go",                      # CDK Go
})


def handler(event, context):
    user_id = event["userId"]
    job_id = event["jobId"]
    bucket = event["artifactsBucket"]
    input_key = event["inputS3Key"]

    update_job_step(ddb, JOBS_TABLE, user_id, job_id, "PREFLIGHT")

    obj = s3.get_object(Bucket=bucket, Key=input_key)
    zip_bytes = obj["Body"].read()

    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise ValueError(f"Zip exceeds {MAX_ZIP_BYTES // (1024 * 1024)} MB limit")

    staging_prefix = f"staging/{user_id}/{job_id}/in"
    file_list = []
    skipped = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            path = info.filename.lstrip("/")
            ext = os.path.splitext(path)[1].lower()

            if info.file_size > MAX_FILE_BYTES:
                skipped.append({"path": path, "reason": "too_large"})
                continue
            if ext not in IaC_EXTENSIONS:
                skipped.append({"path": path, "reason": "not_iac"})
                continue
            if len(file_list) >= MAX_FILES:
                skipped.append({"path": path, "reason": "file_limit_reached"})
                continue

            s3_key = f"{staging_prefix}/{path}"
            s3.put_object(Bucket=bucket, Key=s3_key, Body=zf.read(info.filename))
            file_list.append({"path": path, "s3Key": s3_key, "size": info.file_size, "ext": ext})

    if not file_list:
        raise ValueError("No valid IaC files found in the archive")

    if skipped:
        ddb.Table(JOBS_TABLE).update_item(
            Key={"userId": user_id, "jobId": job_id},
            UpdateExpression="SET skippedFiles = :s",
            ExpressionAttributeValues={":s": skipped},
        )

    return {
        "fileList": file_list,
        "stagingPrefix": staging_prefix,
        "fileCount": len(file_list),
        "skippedCount": len(skipped),
    }
