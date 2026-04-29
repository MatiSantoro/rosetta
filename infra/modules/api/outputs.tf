output "api_endpoint" {
  description = "Base URL of the HTTP API (no trailing slash)."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_id" {
  description = "API Gateway HTTP API ID."
  value       = aws_apigatewayv2_api.this.id
}

output "execution_arn" {
  description = "Execution ARN prefix, used to grant Lambda invoke permissions."
  value       = aws_apigatewayv2_api.this.execution_arn
}
