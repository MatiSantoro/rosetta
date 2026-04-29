import json
import os
import uuid
from datetime import datetime, timezone, timedelta

import boto3
from botocore.config import Config

from ddb_utils import check_and_increment_quota
from s3_utils import presigned_put
from response import ok, err

ddb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version="s3v4"))

JOBS_TABLE = os.environ["JOBS_TABLE"]
QUOTA_TABLE = os.environ["QUOTA_TABLE"]
ARTIFACTS_BUCKET = os.environ["ARTIFACTS_BUCKET"]
DAILY_JOB_QUOTA = int(os.environ.get("DAILY_JOB_QUOTA", "3"))
UPLOAD_TTL = 300  # 5 min presigned URL

VALID_LANGS = {"terraform", "cdk", "cloudformation", "sam"}
VALID_CDK_LANGS = {"typescript", "python", "java", "csharp", "go"}


def handler(event, context):
    user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return err(400, "Invalid JSON body")

    source_lang = (body.get("sourceLang") or "").lower()
    target_lang = (body.get("targetLang") or "").lower()
    source_cdk_lang = (body.get("sourceCdkLang") or "").lower() or None
    target_cdk_lang = (body.get("targetCdkLang") or "").lower() or None

    if source_lang not in VALID_LANGS:
        return err(400, f"Invalid sourceLang. Must be one of: {', '.join(VALID_LANGS)}")
    if target_lang not in VALID_LANGS:
        return err(400, f"Invalid targetLang. Must be one of: {', '.join(VALID_LANGS)}")
    if source_lang == "cdk" and source_cdk_lang not in VALID_CDK_LANGS:
        return err(400, f"sourceCdkLang required for CDK. Must be one of: {', '.join(VALID_CDK_LANGS)}")
    if target_lang == "cdk" and target_cdk_lang not in VALID_CDK_LANGS:
        return err(400, f"targetCdkLang required for CDK. Must be one of: {', '.join(VALID_CDK_LANGS)}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not check_and_increment_quota(ddb, QUOTA_TABLE, user_id, today, DAILY_JOB_QUOTA):
        return err(429, f"Daily job quota of {DAILY_JOB_QUOTA} reached. Try again tomorrow.")

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    expires_at = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
    input_s3_key = f"inputs/{user_id}/{job_id}/upload.zip"

    item = {
        "userId": user_id,
        "jobId": job_id,
        "status": "AWAITING_UPLOAD",
        "sourceLang": source_lang,
        "targetLang": target_lang,
        "inputS3Key": input_s3_key,
        "createdAt": now,
        "updatedAt": now,
        "retryCount": 0,
        "tokensIn": 0,
        "tokensOut": 0,
        "expiresAt": expires_at,
    }
    if source_cdk_lang:
        item["sourceCdkLang"] = source_cdk_lang
    if target_cdk_lang:
        item["targetCdkLang"] = target_cdk_lang

    ddb.Table(JOBS_TABLE).put_item(Item=item)

    upload_url = presigned_put(s3, ARTIFACTS_BUCKET, input_s3_key, UPLOAD_TTL)

    return ok(201, {"jobId": job_id, "uploadUrl": upload_url})
