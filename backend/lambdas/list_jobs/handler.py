import base64
import json
import os

import boto3
from boto3.dynamodb.conditions import Key

from response import ok

ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]
PAGE_SIZE = 20
_INTERNAL_FIELDS = {"expiresAt"}


def handler(event, context):
    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    params = event.get("queryStringParameters") or {}
    next_token = params.get("nextToken")

    kwargs = {
        "KeyConditionExpression": Key("userId").eq(user_id),
        "ScanIndexForward": False,  # newest jobId (UUID v7) first
        "Limit": PAGE_SIZE,
    }
    if next_token:
        try:
            kwargs["ExclusiveStartKey"] = json.loads(base64.b64decode(next_token))
        except Exception:
            pass  # ignore invalid cursor; start from beginning

    resp = ddb.Table(JOBS_TABLE).query(**kwargs)

    items = [{k: v for k, v in item.items() if k not in _INTERNAL_FIELDS} for item in resp["Items"]]
    result = {"items": items}

    if "LastEvaluatedKey" in resp:
        result["nextToken"] = base64.b64encode(
            json.dumps(resp["LastEvaluatedKey"]).encode()
        ).decode()

    return ok(200, result)
