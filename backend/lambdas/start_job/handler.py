import json
import os

import boto3

from ddb_utils import get_job, update_job_status
from s3_utils import object_exists
from response import ok, err

ddb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions")

JOBS_TABLE = os.environ["JOBS_TABLE"]
ARTIFACTS_BUCKET = os.environ["ARTIFACTS_BUCKET"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")


def handler(event, context):
    if not STATE_MACHINE_ARN:
        return err(503, "Translation pipeline not yet configured.")

    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    job_id = event["pathParameters"]["id"]

    job = get_job(ddb, JOBS_TABLE, user_id, job_id)
    if not job:
        return err(404, "Job not found")
    if job["status"] != "AWAITING_UPLOAD":
        return err(409, f"Job cannot be started from status '{job['status']}'")

    if not object_exists(s3, ARTIFACTS_BUCKET, job["inputS3Key"]):
        return err(400, "Upload not found. Upload the zip file before starting the job.")

    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=job_id,
        input=json.dumps({
            "userId": user_id,
            "jobId": job_id,
            "sourceLang": job["sourceLang"],
            "sourceCdkLang": job.get("sourceCdkLang"),
            "targetLang": job["targetLang"],
            "targetCdkLang": job.get("targetCdkLang"),
            "inputS3Key": job["inputS3Key"],
            "artifactsBucket": ARTIFACTS_BUCKET,
            "retryCount": 0,
            "useOpus": False,
            # validateResult initialised so IncrementRetry Pass states can read it safely
            "validateResult": {"ok": True, "errors": [], "warnings": []},
        }),
    )

    update_job_status(ddb, JOBS_TABLE, user_id, job_id, "RUNNING", step="PREFLIGHT")

    return ok(200, {"jobId": job_id, "status": "RUNNING"})
