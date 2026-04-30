data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.env}"
}

module "storage" {
  source = "../../modules/storage"

  name_prefix              = local.name_prefix
  artifacts_retention_days = var.artifacts_retention_days
  cors_allowed_origins     = var.cors_origins
}

module "auth" {
  source = "../../modules/auth"

  name_prefix                    = local.name_prefix
  google_client_id               = var.google_client_id
  google_client_secret_ssm_param = var.google_client_secret_ssm_param
  callback_urls                  = var.frontend_callback_urls
  logout_urls                    = var.frontend_logout_urls
}

module "state_machine" {
  source = "../../modules/state-machine"

  name_prefix           = local.name_prefix
  jobs_table_name       = module.storage.jobs_table_name
  jobs_table_arn        = module.storage.jobs_table_arn
  artifacts_bucket_name = module.storage.artifacts_bucket_name
  artifacts_bucket_arn  = module.storage.artifacts_bucket_arn
  kms_key_arn           = module.storage.kms_key_arn
  translate_model_id    = var.translate_model_id
  opus_model_id         = var.opus_model_id
  compat_model_id       = var.compat_model_id
}

module "lambda" {
  source = "../../modules/lambda"

  name_prefix            = local.name_prefix
  jobs_table_name        = module.storage.jobs_table_name
  jobs_table_arn         = module.storage.jobs_table_arn
  usage_quota_table_name = module.storage.usage_quota_table_name
  usage_quota_table_arn  = module.storage.usage_quota_table_arn
  artifacts_bucket_name  = module.storage.artifacts_bucket_name
  artifacts_bucket_arn   = module.storage.artifacts_bucket_arn
  kms_key_arn            = module.storage.kms_key_arn
  daily_job_quota        = var.daily_job_quota_per_user
  state_machine_arn      = module.state_machine.state_machine_arn
}

module "api" {
  source = "../../modules/api"

  name_prefix        = local.name_prefix
  cognito_issuer     = module.auth.issuer
  cognito_audience   = module.auth.user_pool_client_id
  lambda_invoke_arns = module.lambda.function_invoke_arns
  lambda_arns        = module.lambda.function_arns
  cors_allow_origins = var.cors_origins
}

module "observability" {
  source = "../../modules/observability"

  name_prefix        = local.name_prefix
  alert_email        = var.alert_email
  state_machine_arn  = module.state_machine.state_machine_arn
  state_machine_name = module.state_machine.state_machine_name
  api_id             = module.api.api_id
  jobs_table_name    = module.storage.jobs_table_name
  monthly_budget_usd = var.monthly_budget_usd
  bedrock_budget_usd = var.bedrock_budget_usd

  lambda_function_names = [
    for k in ["preflight", "compatibility_check", "dependency_map",
              "translate", "validate", "package", "mark_failed"] :
    "${local.name_prefix}-sfn-${k}"
  ]
}
