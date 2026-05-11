"""GET /user/profile — returns the current user's tier, quota, and API key."""
from __future__ import annotations

import os
import uuid

import boto3

from ddb_utils import get_user, upsert_user
from response import ok

ddb = boto3.resource("dynamodb")
USERS_TABLE = os.environ["USERS_TABLE"]


def handler(event, context):
    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    user = get_user(ddb, USERS_TABLE, user_id)

    # Generate API key on first access for Pro users (lazy provisioning)
    api_key = user.get("apiKey")
    if not api_key and user.get("tier") == "pro":
        api_key = str(uuid.uuid4()).replace("-", "")
        upsert_user(ddb, USERS_TABLE, user_id, apiKey=api_key)

    return ok(200, {
        "userId":             user_id,
        "tier":               user.get("tier", "free"),
        "quotaLimit":         int(user.get("quotaLimit", 5)),
        "subscriptionStatus": user.get("subscriptionStatus"),
        "apiKey":             api_key if user.get("tier") == "pro" else None,
    })
