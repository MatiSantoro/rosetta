output "jobs_table_name" {
  description = "Name of the Jobs DynamoDB table."
  value       = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  description = "ARN of the Jobs DynamoDB table."
  value       = aws_dynamodb_table.jobs.arn
}

output "jobs_table_gsi_arn" {
  description = "ARN of the status/updatedAt GSI on the Jobs table."
  value       = "${aws_dynamodb_table.jobs.arn}/index/status-updatedAt-index"
}

output "usage_quota_table_name" {
  description = "Name of the UsageQuota DynamoDB table."
  value       = aws_dynamodb_table.usage_quota.name
}

output "usage_quota_table_arn" {
  description = "ARN of the UsageQuota DynamoDB table."
  value       = aws_dynamodb_table.usage_quota.arn
}

output "artifacts_bucket_name" {
  description = "Name of the S3 artifacts bucket."
  value       = aws_s3_bucket.artifacts.id
}

output "artifacts_bucket_arn" {
  description = "ARN of the S3 artifacts bucket."
  value       = aws_s3_bucket.artifacts.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key used by the artifacts bucket and DDB tables."
  value       = aws_kms_key.this.arn
}

output "kms_key_id" {
  description = "ID of the KMS key (for IAM policy refs)."
  value       = aws_kms_key.this.key_id
}
