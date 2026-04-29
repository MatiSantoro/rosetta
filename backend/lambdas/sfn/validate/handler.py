import os

import boto3

from ddb_utils import update_job_step

ddb = boto3.resource("dynamodb")
JOBS_TABLE = os.environ["JOBS_TABLE"]


def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "VALIDATE")

    # TODO: run target-specific validators:
    #   terraform  → terraform fmt -check && terraform validate (binary layer)
    #   cloudformation / sam → cfn-lint (pip layer)
    #   cdk        → structural import/export check + Bedrock self-review pass
    return {"ok": True, "errors": [], "warnings": []}
