"""
POST /jobs/{id}/feedback
Body: {"feedback": "up" | "down"}

Stores a thumbs up/down rating on the job record.
Only the job owner can rate their own job.
Only COMPLETED or COMPLETED_WITH_WARNINGS jobs can be rated.
"""
from __future__ import annotations
import json
import os

import boto3

from ddb_utils import get_job
from response import ok, err

ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]
VALID_FEEDBACK = {"up", "down"}


def handler(event, context):
    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    job_id  = event["pathParameters"]["id"]

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return err(400, "Invalid JSON body")

    feedback = (body.get("feedback") or "").lower()
    if feedback not in VALID_FEEDBACK:
        return err(400, "feedback must be 'up' or 'down'")

    job = get_job(ddb, JOBS_TABLE, user_id, job_id)
    if not job:
        return err(404, "Job not found")
    if job["status"] not in ("COMPLETED", "COMPLETED_WITH_WARNINGS"):
        return err(409, "Feedback can only be submitted for completed translations")

    ddb.Table(JOBS_TABLE).update_item(
        Key={"userId": user_id, "jobId": job_id},
        UpdateExpression="SET feedback = :f",
        ExpressionAttributeValues={":f": feedback},
    )

    return ok(200, {"jobId": job_id, "feedback": feedback})
