output "api_endpoint" {
  value = module.api.api_endpoint
}

output "cognito_user_pool_id" {
  value = module.auth.user_pool_id
}

output "cognito_user_pool_client_id" {
  value = module.auth.user_pool_client_id
}

output "cognito_hosted_ui_domain" {
  value = module.auth.hosted_ui_domain
}

output "cognito_issuer" {
  value = module.auth.issuer
}

output "artifacts_bucket" {
  value = module.storage.artifacts_bucket_name
}

output "jobs_table" {
  value = module.storage.jobs_table_name
}

output "state_machine_arn" {
  value = module.state_machine.state_machine_arn
}

output "dashboard_url" {
  value = module.observability.dashboard_url
}

output "alerts_sns_arn" {
  value = module.observability.sns_topic_arn
}
