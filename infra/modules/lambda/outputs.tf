output "function_arns" {
  description = "Map of handler name → Lambda function ARN."
  value       = { for k, v in aws_lambda_function.handlers : k => v.arn }
}

output "function_invoke_arns" {
  description = "Map of handler name → Lambda invoke ARN (used by API Gateway integrations)."
  value       = { for k, v in aws_lambda_function.handlers : k => v.invoke_arn }
}

output "shared_layer_arn" {
  description = "ARN of the shared Python utility layer."
  value       = aws_lambda_layer_version.shared.arn
}

output "crud_role_arn" {
  description = "IAM role ARN used by all CRUD Lambda functions."
  value       = aws_iam_role.crud.arn
}
