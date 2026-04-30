data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── SNS topic for all alerts ───────────────────────────────────────────────────

resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch Alarms ─────────────────────────────────────────────────────────

# Step Functions execution failures
resource "aws_cloudwatch_metric_alarm" "sfn_failures" {
  alarm_name          = "${var.name_prefix}-sfn-failures"
  alarm_description   = "Step Functions translation pipeline failures"
  namespace           = "AWS/States"
  metric_name         = "ExecutionsFailed"
  dimensions          = { StateMachineArn = var.state_machine_arn }
  statistic           = "Sum"
  period              = 3600   # 1 hour
  evaluation_periods  = 1
  threshold           = var.sfn_failure_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# Lambda errors across all worker functions (composite)
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(var.lambda_function_names)

  alarm_name          = "${var.name_prefix}-lambda-errors-${each.key}"
  alarm_description   = "Lambda ${each.key} error rate"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.key }
  statistic           = "Sum"
  period              = 300   # 5 minutes
  evaluation_periods  = 1
  threshold           = var.lambda_error_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# API Gateway 5xx errors
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name_prefix}-api-5xx"
  alarm_description   = "API Gateway 5xx error rate"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  dimensions          = { ApiId = var.api_id }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# ── CloudWatch Dashboard ───────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.name_prefix

  dashboard_body = jsonencode({
    widgets = [

      # ── Row 1: Pipeline health ──────────────────────────────────────────────
      {
        type   = "metric"
        x = 0
        y = 0
        width = 8
        height = 6
        properties = {
          title  = "Translation Pipeline — Executions"
          region = data.aws_region.current.region
          metrics = [
            ["AWS/States", "ExecutionsStarted",   "StateMachineArn", var.state_machine_arn, { label = "Started",   color = "#2563EB" }],
            ["AWS/States", "ExecutionsSucceeded",  "StateMachineArn", var.state_machine_arn, { label = "Succeeded", color = "#16A34A" }],
            ["AWS/States", "ExecutionsFailed",     "StateMachineArn", var.state_machine_arn, { label = "Failed",    color = "#DC2626" }],
            ["AWS/States", "ExecutionsTimedOut",   "StateMachineArn", var.state_machine_arn, { label = "Timed out", color = "#D97706" }],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 3600
        }
      },

      {
        type   = "metric"
        x = 8
        y = 0
        width = 8
        height = 6
        properties = {
          title  = "Translation Pipeline — Duration (p50 / p95)"
          region = data.aws_region.current.region
          metrics = [
            ["AWS/States", "ExecutionTime", "StateMachineArn", var.state_machine_arn, { stat = "p50", label = "p50" }],
            ["AWS/States", "ExecutionTime", "StateMachineArn", var.state_machine_arn, { stat = "p95", label = "p95", color = "#D97706" }],
          ]
          view   = "timeSeries"
          period = 3600
        }
      },

      {
        type   = "metric"
        x = 16
        y = 0
        width = 8
        height = 6
        properties = {
          title  = "API Gateway — Requests & Errors"
          region = data.aws_region.current.region
          metrics = [
            ["AWS/ApiGateway", "Count",    "ApiId", var.api_id, { label = "Requests", color = "#2563EB" }],
            ["AWS/ApiGateway", "4XXError", "ApiId", var.api_id, { label = "4xx",      color = "#D97706" }],
            ["AWS/ApiGateway", "5XXError", "ApiId", var.api_id, { label = "5xx",      color = "#DC2626" }],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 300
        }
      },

      # ── Row 2: Lambda health ────────────────────────────────────────────────
      {
        type   = "metric"
        x = 0
        y = 6
        width = 12
        height = 6
        properties = {
          title  = "Lambda — Errors (worker functions)"
          region = data.aws_region.current.region
          metrics = [for fn in var.lambda_function_names :
            ["AWS/Lambda", "Errors", "FunctionName", fn, { label = fn, stat = "Sum" }]
          ]
          view   = "timeSeries"
          period = 300
        }
      },

      {
        type   = "metric"
        x = 12
        y = 6
        width = 12
        height = 6
        properties = {
          title  = "Lambda — Duration p95 (worker functions)"
          region = data.aws_region.current.region
          metrics = [for fn in var.lambda_function_names :
            ["AWS/Lambda", "Duration", "FunctionName", fn, { label = fn, stat = "p95" }]
          ]
          view   = "timeSeries"
          period = 300
        }
      },

      # ── Row 3: Bedrock ──────────────────────────────────────────────────────
      {
        type   = "metric"
        x = 0
        y = 12
        width = 12
        height = 6
        properties = {
          title  = "Bedrock — Invocations"
          region = data.aws_region.current.region
          metrics = [
            ["AWS/Bedrock", "Invocations", { stat = "Sum", label = "Total invocations" }],
          ]
          view   = "timeSeries"
          period = 3600
        }
      },

      {
        type   = "metric"
        x = 12
        y = 12
        width = 12
        height = 6
        properties = {
          title  = "Bedrock — Latency p95"
          region = data.aws_region.current.region
          metrics = [
            ["AWS/Bedrock", "InvocationLatency", { stat = "p95", label = "p95 latency" }],
          ]
          view   = "timeSeries"
          period = 3600
        }
      },

    ]
  })
}

# ── AWS Budgets ────────────────────────────────────────────────────────────────

resource "aws_budgets_budget" "total_monthly" {
  name         = "${var.name_prefix}-total-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 90
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

resource "aws_budgets_budget" "bedrock" {
  name         = "${var.name_prefix}-bedrock"
  budget_type  = "COST"
  limit_amount = tostring(var.bedrock_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "Service"
    values = ["Amazon Bedrock"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}
