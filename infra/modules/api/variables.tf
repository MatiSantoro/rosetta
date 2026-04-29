variable "name_prefix" {
  description = "Prefix for all resource names, e.g. 'rosetta-dev'."
  type        = string
}

variable "cognito_issuer" {
  description = "Cognito User Pool issuer URL (https://...). Used by the JWT authorizer."
  type        = string
}

variable "cognito_audience" {
  description = "Cognito app client ID. Used as the JWT audience claim."
  type        = string
}

variable "lambda_invoke_arns" {
  description = "Map of handler name → Lambda invoke ARN."
  type        = map(string)
}

variable "lambda_arns" {
  description = "Map of handler name → Lambda function ARN (for resource-based permission)."
  type        = map(string)
}

variable "cors_allow_origins" {
  description = "Origins allowed by CORS on the HTTP API (should match the SPA origin)."
  type        = list(string)
}

variable "throttle_burst_limit" {
  description = "API Gateway stage burst limit (requests/second)."
  type        = number
  default     = 50
}

variable "throttle_rate_limit" {
  description = "API Gateway stage rate limit (requests/second)."
  type        = number
  default     = 10
}
