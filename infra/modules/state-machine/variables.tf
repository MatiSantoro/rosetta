variable "name_prefix" {
  type = string
}

variable "jobs_table_name" {
  type = string
}

variable "jobs_table_arn" {
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

variable "translate_model_id" {
  description = "Bedrock model ID for file translation (Claude Sonnet 4.6)."
  type        = string
  default     = "us.anthropic.claude-sonnet-4-6"
}

variable "opus_model_id" {
  description = "Bedrock model ID for translation escalation on 3rd retry (Claude Opus 4.7)."
  type        = string
  default     = "us.anthropic.claude-opus-4-7"
}

variable "compat_model_id" {
  description = "Bedrock model ID for SAM compatibility checks (Claude Haiku 4.5)."
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "log_retention_days" {
  type    = number
  default = 30
}
