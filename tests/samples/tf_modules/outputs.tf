output "bucket_name" {
  description = "Name of the artifacts S3 bucket."
  value       = module.storage.bucket_name
}

output "jobs_table_name" {
  description = "Name of the DynamoDB jobs table."
  value       = module.database.jobs_table_name
}

output "processor_function_arn" {
  description = "ARN of the processor Lambda function."
  value       = module.lambda.function_arn
}

output "processor_function_name" {
  description = "Name of the processor Lambda function."
  value       = module.lambda.function_name
}
