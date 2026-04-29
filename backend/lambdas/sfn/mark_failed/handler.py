import json
import os

import boto3

from ddb_utils import update_job_status

ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]


def handler(event, context):
    user_id = event.get("userId", "")
    job_id = event.get("jobId", "")

    # When called via Catch, $.error = {"Error": "...", "Cause": "..."}
    error_info = event.get("error") or {}
    cause = error_info.get("Cause", "")
    try:
        # Lambda encodes errorMessage as JSON string in Cause
        error_detail = json.loads(cause).get("errorMessage", cause)
    except (json.JSONDecodeError, TypeError, AttributeError):
        error_detail = cause

    error_msg = (
        event.get("errorMsg")       # set explicitly by MarkJobIncompatible state
        or error_detail
        or error_info.get("Error")
        or "An unexpected pipeline error occurred"
    )

    if user_id and job_id:
        update_job_status(
            ddb, JOBS_TABLE, user_id, job_id, "FAILED",
            step="FAILED",
            error_msg=str(error_msg)[:1000],
        )

    return {"status": "FAILED", "errorMsg": str(error_msg)[:200]}
