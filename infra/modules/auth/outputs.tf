output "user_pool_id" {
  description = "Cognito User Pool ID."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN. Used by API Gateway JWT authorizer."
  value       = aws_cognito_user_pool.this.arn
}

output "user_pool_endpoint" {
  description = "Cognito User Pool endpoint."
  value       = aws_cognito_user_pool.this.endpoint
}

output "user_pool_client_id" {
  description = "App client ID for the SPA (PKCE public client)."
  value       = aws_cognito_user_pool_client.spa.id
}

output "hosted_ui_domain" {
  description = "Cognito-managed Hosted UI domain (no protocol)."
  value       = "${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.region}.amazoncognito.com"
}

output "issuer" {
  description = "Issuer URL (https://...) for the User Pool. Used by JWT authorizers."
  value       = "https://${aws_cognito_user_pool.this.endpoint}"
}
