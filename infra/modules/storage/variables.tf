variable "name_prefix" {
  description = "Prefix for resource names, e.g. 'rosetta-dev'."
  type        = string
}

variable "artifacts_retention_days" {
  description = "Lifecycle expiration in days for input/staging/output artifacts."
  type        = number
  default     = 7
}

variable "cors_allowed_origins" {
  description = "Origins allowed to PUT/GET artifact objects via presigned URLs."
  type        = list(string)
  default     = []
}
