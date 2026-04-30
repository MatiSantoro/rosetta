variable "name_prefix" {
  type = string
}

variable "alert_email" {
  description = "Email address that receives alarm and budget notifications."
  type        = string
}

variable "state_machine_arn" {
  type = string
}

variable "state_machine_name" {
  type = string
}

variable "lambda_function_names" {
  description = "List of Lambda function names to monitor."
  type        = list(string)
}

variable "api_id" {
  description = "API Gateway HTTP API ID."
  type        = string
}

variable "jobs_table_name" {
  type = string
}

# ── Budget thresholds ──────────────────────────────────────────────────────────

variable "monthly_budget_usd" {
  description = "Total monthly AWS spend budget in USD."
  type        = number
  default     = 100
}

variable "bedrock_budget_usd" {
  description = "Monthly Bedrock spend budget in USD."
  type        = number
  default     = 50
}

# ── Alarm thresholds ───────────────────────────────────────────────────────────

variable "sfn_failure_threshold" {
  description = "Number of SFN execution failures in 1 hour before alarming."
  type        = number
  default     = 5
}

variable "lambda_error_threshold" {
  description = "Number of Lambda errors in 5 minutes before alarming."
  type        = number
  default     = 10
}

variable "log_retention_days" {
  type    = number
  default = 30
}
