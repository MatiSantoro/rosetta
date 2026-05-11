from __future__ import annotations
import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

from ddb_utils import get_job, get_user, update_job_status
from s3_utils import object_exists
from response import ok, err

ddb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions")

JOBS_TABLE        = os.environ["JOBS_TABLE"]
USERS_TABLE       = os.environ["USERS_TABLE"]
ARTIFACTS_BUCKET  = os.environ["ARTIFACTS_BUCKET"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

# Max concurrent RUNNING jobs for free-tier users.
# Pro users always start immediately — this check is skipped for them.
FREE_MAX_CONCURRENT = int(os.environ.get("FREE_MAX_CONCURRENT", "3"))


def _count_running_free_jobs() -> int:
    """Count how many free-tier jobs are currently RUNNING across all users."""
    resp = ddb.Table(JOBS_TABLE).query(
        IndexName="status-updatedAt-index",
        KeyConditionExpression="#s = :running",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":running": "RUNNING"},
        Select="COUNT",
    )
    return resp.get("Count", 0)


def handler(event, context):
    if not STATE_MACHINE_ARN:
        return err(503, "Translation pipeline not yet configured.")

    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    job_id  = event["pathParameters"]["id"]

    job = get_job(ddb, JOBS_TABLE, user_id, job_id)
    if not job:
        return err(404, "Job not found")
    if job["status"] != "AWAITING_UPLOAD":
        return err(409, f"Job cannot be started from status '{job['status']}'")

    if not object_exists(s3, ARTIFACTS_BUCKET, job["inputS3Key"]):
        return err(400, "Upload not found. Upload the zip file before starting the job.")

    # Priority gate: Pro jobs always start immediately.
    # Free-tier jobs are held back if the system is busy so Pro users
    # never wait behind free jobs. Upgrade removes this limit.
    user = get_user(ddb, USERS_TABLE, user_id)
    if user.get("tier", "free") != "pro" and not user.get("isAdmin", False):
        running = _count_running_free_jobs()
        if running >= FREE_MAX_CONCURRENT:
            return err(429, "The system is busy — please try again in a moment. "
                            "Upgrade to Pro for guaranteed instant processing.")

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
            "planResult": {"units": [], "symbolTable": {}, "planNotes": ""},
        }),
    )

    update_job_status(ddb, JOBS_TABLE, user_id, job_id, "RUNNING", step="PREFLIGHT")

    return ok(200, {"jobId": job_id, "status": "RUNNING"})
