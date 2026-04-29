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
  description = "Hard cap on jobs per user per day."
  type        = number
  default     = 3
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
