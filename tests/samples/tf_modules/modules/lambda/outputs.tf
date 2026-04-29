output "function_arn" {
  description = "ARN of the processor Lambda function."
  value       = aws_lambda_function.processor.arn
}

output "function_name" {
  description = "Name of the processor Lambda function."
  value       = aws_lambda_function.processor.function_name
}

output "role_arn" {
  description = "ARN of the Lambda execution role."
  value       = aws_iam_role.processor.arn
}
