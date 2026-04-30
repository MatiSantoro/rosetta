output "artifacts_bucket" {
  description = "Name of the S3 bucket holding job artifacts."
  value       = module.storage.artifacts_bucket_name
}

output "jobs_table" {
  description = "DynamoDB table name for jobs."
  value       = module.storage.jobs_table_name
}

output "usage_quota_table" {
  description = "DynamoDB table name for per-user daily quota counters."
  value       = module.storage.usage_quota_table_name
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID. Used by the frontend Amplify auth config."
  value       = module.auth.user_pool_id
}

output "cognito_user_pool_client_id" {
  description = "Cognito User Pool app client ID (PKCE public client)."
  value       = module.auth.user_pool_client_id
}

output "cognito_hosted_ui_domain" {
  description = "Hosted UI domain (Cognito-managed). Use with the Google federated sign-in flow."
  value       = module.auth.hosted_ui_domain
}

output "cognito_issuer" {
  description = "Issuer URL for the Cognito User Pool. Used by API Gateway JWT authorizer."
  value       = module.auth.issuer
}

output "api_endpoint" {
  description = "Base URL of the HTTP API. Use this to curl-test the endpoints."
  value       = module.api.api_endpoint
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN."
  value       = module.state_machine.state_machine_arn
}

output "dashboard_url" {
  description = "CloudWatch dashboard URL."
  value       = module.observability.dashboard_url
}

output "alerts_sns_arn" {
  description = "SNS topic ARN for alerts."
  value       = module.observability.sns_topic_arn
}
