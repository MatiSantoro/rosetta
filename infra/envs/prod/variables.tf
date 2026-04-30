variable "project" {
  type    = string
  default = "rosetta"
}

variable "env" {
  type    = string
  default = "prod"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "google_client_id" {
  description = "Google OAuth 2.0 client ID."
  type        = string
}

variable "google_client_secret_ssm_param" {
  type    = string
  default = "/rosetta/prod/google_oauth_client_secret"
}

variable "frontend_callback_urls" {
  type    = list(string)
  default = ["https://rosetta-translate.com/auth/callback"]
}

variable "frontend_logout_urls" {
  type    = list(string)
  default = ["https://rosetta-translate.com/"]
}

variable "cors_origins" {
  type    = list(string)
  default = ["https://rosetta-translate.com"]
}

variable "artifacts_retention_days" {
  type    = number
  default = 7
}

variable "daily_job_quota_per_user" {
  type    = number
  default = 3
}

variable "translate_model_id" {
  type    = string
  default = "us.anthropic.claude-sonnet-4-6"
}

variable "opus_model_id" {
  type    = string
  default = "us.anthropic.claude-opus-4-7"
}

variable "compat_model_id" {
  type    = string
  default = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

# ------- Observability -------

variable "alert_email" {
  description = "Email for CloudWatch alarms and budget notifications."
  type        = string
  default     = "rosetta.translate.app@gmail.com"
}

variable "monthly_budget_usd" {
  type    = number
  default = 200
}

variable "bedrock_budget_usd" {
  type    = number
  default = 100
}
