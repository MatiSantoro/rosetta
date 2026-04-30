"""
Check that every resource type in the uploaded IaC is serverless-compatible.
Only invoked when the target format is SAM.
Uses Bedrock Haiku 4.5 for cheap, fast classification.
"""
import json
import os
import re

import boto3

from ddb_utils import update_job_step

s3      = boto3.client("s3")
ddb     = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE       = os.environ["JOBS_TABLE"]
COMPAT_MODEL_ID  = os.environ.get("COMPAT_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

SYSTEM_PROMPT = """\
You are an AWS serverless architecture expert.

Determine whether a given set of AWS resource types can ALL be expressed as serverless components compatible with AWS SAM (Serverless Application Model).

Serverless-compatible: Lambda, API Gateway (REST/HTTP), DynamoDB, S3, SQS, SNS, EventBridge, Step Functions, Cognito, CloudFront, SES, SSM Parameter Store, Secrets Manager, AppSync, Kinesis Data Streams/Firehose, IoT Core.

NOT serverless-compatible (reject these): EC2 instances, ECS on EC2, RDS (non-Aurora Serverless), ElastiCache, Redshift, NAT Gateway, ALB/NLB/CLB, EMR, MSK, OpenSearch on EC2.

Respond with a JSON object ONLY — no explanation, no markdown:
{"compatible": true|false, "reasons": ["<reason if false>", ...]}"""


def extract_resource_types(text: str) -> list[str]:
    types: set[str] = set()
    # CloudFormation / SAM  →  Type: AWS::Service::Resource
    types.update(re.findall(r"Type:\s*(AWS::\S+)", text))
    # Terraform             →  resource "aws_service_resource"
    types.update(re.findall(r'resource\s+"(aws_\S+)"', text))
    return sorted(types)


def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "COMPAT_CHECK")

    bucket    = event["artifactsBucket"]
    file_list = event.get("preflightResult", {}).get("fileList", [])

    combined = []
    for f in file_list[:20]:   # cap to keep prompt small
        try:
            body = (
                s3.get_object(Bucket=bucket, Key=f["s3Key"])["Body"]
                .read()
                .decode("utf-8", errors="replace")
            )
            combined.append(body)
        except Exception:
            continue

    resource_types = extract_resource_types("\n\n".join(combined))

    if not resource_types:
        return {"compatible": True, "reasons": ["No resource types detected — assuming compatible"]}

    user_msg = (
        "Resource types found in the uploaded IaC:\n"
        + json.dumps(resource_types, indent=2)
        + "\n\nAre ALL of these serverless-compatible for AWS SAM?"
    )

    response = bedrock.converse(
        modelId=COMPAT_MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        inferenceConfig={"maxTokens": 256},
    )

    raw = response["output"]["message"]["content"][0]["text"].strip()

    try:
        result = json.loads(raw)
        if "compatible" not in result:
            raise ValueError("missing compatible key")
    except (json.JSONDecodeError, ValueError):
        # Fail open — don't block users on a classification parse error
        result = {"compatible": True, "reasons": ["Classification response could not be parsed — defaulting to compatible"]}

    return result
