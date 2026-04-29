from botocore.exceptions import ClientError


def object_exists(s3_client, bucket: str, key: str) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def presigned_put(s3_client, bucket: str, key: str, ttl: int = 300) -> str:
    return s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": "application/zip"},
        ExpiresIn=ttl,
    )


def presigned_get(s3_client, bucket: str, key: str, ttl: int = 300) -> str:
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=ttl,
    )
