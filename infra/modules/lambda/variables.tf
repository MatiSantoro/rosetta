variable "name_prefix" {
  description = "Prefix for all resource names, e.g. 'rosetta-dev'."
  type        = string
}

variable "jobs_table_name" {
  type = string
}

variable "jobs_table_arn" {
  type = string
}

variable "usage_quota_table_name" {
  type = string
}

variable "usage_quota_table_arn" {
  type = string
}

variable "artifacts_bucket_name" {
  type = string
}

variable "artifacts_bucket_arn" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "daily_job_quota" {
  description = "Default monthly job cap for free-tier users (passed as FREE_JOB_QUOTA env var)."
  type        = number
  default     = 5
}

variable "state_machine_arn" {
  description = "Step Functions state machine ARN. Empty string until the state machine module is added."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log group retention in days."
  type        = number
  default     = 30
}

variable "users_table_name" {
  description = "Name of the Users DynamoDB table."
  type        = string
}

variable "users_table_arn" {
  description = "ARN of the Users DynamoDB table."
  type        = string
}

variable "app_url" {
  description = "Base URL of the Rosetta frontend application."
  type        = string
  default     = "https://rosetta-translate.com"
}

variable "ssm_prefix" {
  description = "SSM Parameter Store prefix for runtime secrets (e.g. /rosetta/prod)."
  type        = string
  default     = "/rosetta/prod"
}
