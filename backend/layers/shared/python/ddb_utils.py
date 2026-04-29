from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError


def check_and_increment_quota(ddb, table_name: str, user_id: str, date: str, cap: int) -> bool:
    """Atomically increments the daily job counter. Returns False if the cap is already reached."""
    table = ddb.Table(table_name)
    expires_at = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
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
