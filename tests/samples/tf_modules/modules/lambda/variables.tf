variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "jobs_table_name" {
  description = "Name of the DynamoDB jobs table (from database module)."
  type        = string
}

variable "jobs_table_arn" {
  description = "ARN of the DynamoDB jobs table (from database module)."
  type        = string
}

variable "bucket_name" {
  description = "Name of the S3 artifacts bucket (from storage module)."
  type        = string
}

variable "bucket_arn" {
  description = "ARN of the S3 artifacts bucket (from storage module)."
  type        = string
}
