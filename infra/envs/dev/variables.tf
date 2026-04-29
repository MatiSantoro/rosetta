variable "project" {
  description = "Project name, used as a prefix for all resources."
  type        = string
  default     = "rosetta"
}

variable "env" {
  description = "Environment name (dev, prod)."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region. Single-region project."
  type        = string
  default     = "us-east-1"
}

# ------- Auth -------

variable "google_client_id" {
  description = "Google OAuth 2.0 client ID for Cognito federation."
  type        = string
}

variable "google_client_secret_ssm_param" {
  description = "Name of the SSM SecureString parameter that holds the Google OAuth client secret. Create this manually before apply."
  type        = string
  default     = "/rosetta/dev/google_oauth_client_secret"
}

variable "frontend_callback_urls" {
  description = "Allowed callback URLs for the Cognito app client (post-login redirects)."
  type        = list(string)
  # Default to localhost for early dev. Add the Amplify URL once it is created.
  default = ["http://localhost:5173/auth/callback"]
}

variable "frontend_logout_urls" {
  description = "Allowed logout URLs for the Cognito app client."
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

# ------- Storage -------

variable "artifacts_retention_days" {
  description = "How long to keep input/staging/output artifacts in S3 before lifecycle expiration."
  type        = number
  default     = 7
}

# ------- CORS -------

variable "cors_origins" {
  description = "Allowed CORS origins for API Gateway — scheme+host+port only, no paths (e.g. http://localhost:5173)."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

# ------- Limits -------

variable "daily_job_quota_per_user" {
  description = "Hard cap on jobs per user per day."
  type        = number
  default     = 3
}
