import io
import os
import zipfile

import boto3

from ddb_utils import update_job_status

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]


def handler(event, context):
    user_id = event["userId"]
    job_id = event["jobId"]
    bucket = event["artifactsBucket"]
    status = event.get("status", "COMPLETED")

    out_prefix = f"staging/{user_id}/{job_id}/out/"
    output_zip_key = f"outputs/{user_id}/{job_id}/result.zip"

    paginator = s3.get_paginator("list_objects_v2")
    zip_buffer = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for page in paginator.paginate(Bucket=bucket, Prefix=out_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                relative = key[len(out_prefix):]
                if not relative:
                    continue
                body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                zf.writestr(relative, body)
                file_count += 1

    if file_count == 0:
        raise RuntimeError("No output files found to package")

    zip_buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=output_zip_key, Body=zip_buffer.read())

    update_job_status(
        ddb, JOBS_TABLE, user_id, job_id, status,
        step="DONE",
        output_s3_key=output_zip_key,
    )

    return {"outputS3Key": output_zip_key, "status": status, "fileCount": file_count}
