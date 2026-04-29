import os

import boto3
from botocore.config import Config

from ddb_utils import get_job
from s3_utils import presigned_get
from response import ok, err

ddb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version="s3v4"))

JOBS_TABLE = os.environ["JOBS_TABLE"]
ARTIFACTS_BUCKET = os.environ["ARTIFACTS_BUCKET"]
DOWNLOAD_TTL = 300  # 5 min presigned URL

_COMPLETED_STATUSES = {"COMPLETED", "COMPLETED_WITH_WARNINGS"}


def handler(event, context):
    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    job_id = event["pathParameters"]["id"]

    job = get_job(ddb, JOBS_TABLE, user_id, job_id)
    if not job:
        return err(404, "Job not found")
    if job["status"] not in _COMPLETED_STATUSES:
        return err(409, f"Job is not ready for download (status: {job['status']})")

    output_key = job.get("outputS3Key")
    if not output_key:
        return err(500, "Output artifact missing — contact support")

    download_url = presigned_get(s3, ARTIFACTS_BUCKET, output_key, DOWNLOAD_TTL)

    return ok(200, {"downloadUrl": download_url, "status": job["status"]})
