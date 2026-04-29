locals {
  # route key → Lambda handler name
  routes = {
    "POST /jobs"              = "create_job"
    "POST /jobs/{id}/start"   = "start_job"
    "GET /jobs/{id}/download" = "get_download"
    "GET /jobs/{id}"          = "get_job"
    "GET /jobs"               = "list_jobs"
  }
}

# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"
  description   = "Rosetta IaC translation API"

  cors_configuration {
    allow_origins     = var.cors_allow_origins
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_headers     = ["Authorization", "Content-Type"]
    expose_headers    = ["Content-Type"]
    allow_credentials = false
    max_age           = 300
  }
}

# ---------------------------------------------------------------------------
# Cognito JWT authorizer
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.this.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-jwt"

  jwt_configuration {
    issuer   = var.cognito_issuer
    audience = [var.cognito_audience]
  }
}

# ---------------------------------------------------------------------------
# Lambda integrations (one per handler)
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_integration" "handlers" {
  for_each = local.routes

  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arns[each.value]
  payload_format_version = "2.0"
}

# ---------------------------------------------------------------------------
# Routes (all JWT-protected)
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_route" "routes" {
  for_each = local.routes

  api_id             = aws_apigatewayv2_api.this.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.handlers[each.key].id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

# ---------------------------------------------------------------------------
# Default stage with access logging and throttling
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${var.name_prefix}"
  retention_in_days = 30
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = var.throttle_burst_limit
    throttling_rate_limit  = var.throttle_rate_limit
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      durationMs     = "$context.responseLatency"
      userAgent      = "$context.identity.userAgent"
      errorMessage   = "$context.error.message"
    })
  }
}

# ---------------------------------------------------------------------------
# Lambda resource-based permissions (allow API GW to invoke each function)
# ---------------------------------------------------------------------------

resource "aws_lambda_permission" "apigw" {
  for_each = var.lambda_arns

  statement_id  = "AllowAPIGatewayInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = each.value
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
