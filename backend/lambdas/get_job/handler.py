import os

import boto3

from ddb_utils import get_job
from response import ok, err

ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]

_INTERNAL_FIELDS = {"expiresAt"}


def handler(event, context):
    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    job_id = event["pathParameters"]["id"]

    job = get_job(ddb, JOBS_TABLE, user_id, job_id)
    if not job:
        return err(404, "Job not found")

    return ok(200, {k: v for k, v in job.items() if k not in _INTERNAL_FIELDS})
