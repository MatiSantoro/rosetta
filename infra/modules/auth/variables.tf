variable "name_prefix" {
  description = "Prefix for resource names, e.g. 'rosetta-dev'."
  type        = string
}

variable "google_client_id" {
  description = "Google OAuth 2.0 client ID."
  type        = string
}

variable "google_client_secret_ssm_param" {
  description = "Name of the SSM SecureString parameter holding the Google OAuth client secret. Must exist before apply."
  type        = string
}

variable "callback_urls" {
  description = "Allowed callback URLs for the Cognito app client."
  type        = list(string)
}

variable "logout_urls" {
  description = "Allowed logout URLs for the Cognito app client."
  type        = list(string)
}

variable "custom_domain" {
  description = "Custom domain for the Cognito Hosted UI, e.g. 'rosetta-translate.com'. Leave empty to use the Cognito-managed domain."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN (us-east-1) for the custom Cognito domain. Required when custom_domain is set."
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for the custom domain. Required when custom_domain is set."
  type        = string
  default     = ""
}

variable "advanced_security_mode" {
  description = "Cognito advanced security mode. OFF for free tier; AUDIT or ENFORCED costs $0.05/MAU."
  type        = string
  default     = "OFF"

  validation {
    condition     = contains(["OFF", "AUDIT", "ENFORCED"], var.advanced_security_mode)
    error_message = "advanced_security_mode must be OFF, AUDIT, or ENFORCED."
  }
}

variable "access_token_validity_minutes" {
  description = "Access token lifetime in minutes."
  type        = number
  default     = 60
}

variable "id_token_validity_minutes" {
  description = "ID token lifetime in minutes."
  type        = number
  default     = 60
}

variable "refresh_token_validity_days" {
  description = "Refresh token lifetime in days."
  type        = number
  default     = 30
}
