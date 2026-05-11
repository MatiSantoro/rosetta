from __future__ import annotations

from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError


def check_and_increment_quota(ddb, table_name: str, user_id: str, date: str, cap: int) -> bool:
    """Atomically increments the monthly job counter. Returns False if cap reached.
    date should be YYYY-MM format for monthly tracking."""
    table = ddb.Table(table_name)
    # TTL = 40 days from now (covers full month + buffer)
    expires_at = int((datetime.now(timezone.utc) + timedelta(days=40)).timestamp())
    try:
        table.update_item(
            Key={"userId": user_id, "date": date},
            UpdateExpression="ADD jobCount :one SET expiresAt = if_not_exists(expiresAt, :exp)",
            ConditionExpression="attribute_not_exists(jobCount) OR jobCount < :cap",
            ExpressionAttributeValues={":one": 1, ":exp": expires_at, ":cap": cap},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def decrement_quota(ddb, table_name: str, user_id: str, date: str) -> None:
    """Decrements the monthly job counter by 1 (minimum 0). Call on job failure to refund the slot.
    date should be YYYY-MM format for monthly tracking."""
    table = ddb.Table(table_name)
    try:
        table.update_item(
            Key={"userId": user_id, "date": date},
            UpdateExpression="ADD jobCount :neg",
            ConditionExpression="attribute_exists(jobCount) AND jobCount > :zero",
            ExpressionAttributeValues={":neg": -1, ":zero": 0},
        )
    except Exception:
        # If the item doesn't exist or count is already 0, silently ignore
        pass


def get_job(ddb, table_name: str, user_id: str, job_id: str) -> dict | None:
    """Returns the job item or None if not found / wrong owner."""
    resp = ddb.Table(table_name).get_item(Key={"userId": user_id, "jobId": job_id})
    return resp.get("Item")


def update_job_step(ddb, table_name: str, user_id: str, job_id: str, step: str) -> None:
    """Updates only the step and updatedAt fields — avoids touching status."""
    now = datetime.now(timezone.utc).isoformat()
    ddb.Table(table_name).update_item(
        Key={"userId": user_id, "jobId": job_id},
        UpdateExpression="SET #step = :step, updatedAt = :now",
        ExpressionAttributeNames={"#step": "step"},
        ExpressionAttributeValues={":step": step, ":now": now},
    )


def add_job_tokens(ddb, table_name: str, user_id: str, job_id: str, tokens_in: int, tokens_out: int) -> None:
    """Atomically increments the token usage counters."""
    ddb.Table(table_name).update_item(
        Key={"userId": user_id, "jobId": job_id},
        UpdateExpression="ADD tokensIn :ti, tokensOut :to",
        ExpressionAttributeValues={":ti": tokens_in, ":to": tokens_out},
    )


def update_job_status(
    ddb,
    table_name: str,
    user_id: str,
    job_id: str,
    status: str,
    *,
    step: str | None = None,
    error_msg: str | None = None,
    output_s3_key: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    set_parts = ["#s = :status", "updatedAt = :now"]
    names = {"#s": "status"}
    values = {":status": status, ":now": now}

    if step is not None:
        set_parts.append("#step = :step")
        names["#step"] = "step"
        values[":step"] = step
    if error_msg is not None:
        set_parts.append("errorMsg = :err")
        values[":err"] = error_msg
    if output_s3_key is not None:
        set_parts.append("outputS3Key = :osk")
        values[":osk"] = output_s3_key

    ddb.Table(table_name).update_item(
        Key={"userId": user_id, "jobId": job_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


# ── Users table ───────────────────────────────────────────────────────────────

def get_user(ddb, table_name: str, user_id: str) -> dict:
    """Returns the user record. Returns defaults if not found (free tier)."""
    resp = ddb.Table(table_name).get_item(Key={"userId": user_id})
    return resp.get("Item", {
        "userId":             user_id,
        "tier":               "free",
        "quotaLimit":         5,
        "apiKey":             None,
        "stripeCustomerId":   None,
        "subscriptionStatus": None,
    })


def upsert_user(ddb, table_name: str, user_id: str, **attrs) -> None:
    """Create or update a user record with the provided attributes."""
    now = datetime.now(timezone.utc).isoformat()
    set_parts = ["updatedAt = :now"]
    values = {":now": now}
    names = {}

    for k, v in attrs.items():
        placeholder = f":_{k}"
        set_parts.append(f"#{k} = {placeholder}")
        values[placeholder] = v
        names[f"#{k}"] = k

    set_parts.append("createdAt = if_not_exists(createdAt, :now)")

    kwargs: dict = {
        "Key":                    {"userId": user_id},
        "UpdateExpression":       "SET " + ", ".join(set_parts),
        "ExpressionAttributeValues": values,
    }
    if names:
        kwargs["ExpressionAttributeNames"] = names

    ddb.Table(table_name).update_item(**kwargs)


def get_user_by_stripe_id(ddb, table_name: str, stripe_customer_id: str) -> dict | None:
    """Look up a user by Stripe customer ID using GSI."""
    from boto3.dynamodb.conditions import Key as DdbKey
    resp = ddb.Table(table_name).query(
        IndexName="stripeCustomerId-index",
        KeyConditionExpression=DdbKey("stripeCustomerId").eq(stripe_customer_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None
