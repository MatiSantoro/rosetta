data "aws_region" "current" {}

# Read the Google OAuth client secret from SSM. The parameter must be created
# manually before the first apply (see infra/bootstrap/README.md). Using a data
# source keeps the secret out of source control; it WILL appear in tfstate, so
# the tfstate bucket must remain encrypted and access-restricted.
data "aws_ssm_parameter" "google_client_secret" {
  name            = var.google_client_secret_ssm_param
  with_decryption = true
}

# ---------------------------------------------------------------------------
# Cognito User Pool
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 3
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_pool_add_ons {
    advanced_security_mode = var.advanced_security_mode
  }

  lifecycle {
    # Schema changes after creation force replacement. Email is auto-defined
    # via username_attributes; ignore drift if the provider surfaces any.
    ignore_changes = [schema]
  }
}

# ---------------------------------------------------------------------------
# Google federated identity provider
# ---------------------------------------------------------------------------

resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.this.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id                     = var.google_client_id
    client_secret                 = data.aws_ssm_parameter.google_client_secret.value
    authorize_scopes              = "openid email profile"
    attributes_url_add_attributes = "true"
  }

  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    username       = "sub"
    name           = "name"
    picture        = "picture"
  }
}

# ---------------------------------------------------------------------------
# App client (PKCE public client for the SPA)
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool_client" "spa" {
  name         = "${var.name_prefix}-spa"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  supported_identity_providers = [
    "COGNITO",
    aws_cognito_identity_provider.google.provider_name,
  ]

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  access_token_validity  = var.access_token_validity_minutes
  id_token_validity      = var.id_token_validity_minutes
  refresh_token_validity = var.refresh_token_validity_days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  read_attributes  = ["email", "email_verified", "name", "picture"]
  write_attributes = ["email", "name", "picture"]
}

# ---------------------------------------------------------------------------
# Hosted UI on a Cognito-managed domain. (Custom domains require an ACM cert
# in us-east-1 and DNS work; defer to post-MVP.) The domain prefix must be
# globally unique within the region.
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.name_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}
