output "bucket_name" {
  description = "Name of the data S3 bucket."
  value       = aws_s3_bucket.data.id
}

output "table_name" {
  description = "Name of the DynamoDB jobs table."
  value       = aws_dynamodb_table.jobs.name
}

output "function_arn" {
  description = "ARN of the processor Lambda function."
  value       = aws_lambda_function.processor.arn
}
