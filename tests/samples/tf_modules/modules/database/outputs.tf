output "jobs_table_name" {
  value = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  value = aws_dynamodb_table.jobs.arn
}

output "quota_table_name" {
  value = aws_dynamodb_table.quota.name
}

output "quota_table_arn" {
  value = aws_dynamodb_table.quota.arn
}
