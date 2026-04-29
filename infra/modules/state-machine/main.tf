data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  worker_names = toset([
    "preflight",
    "compatibility_check",
    "dependency_map",
    "translate",
    "validate",
    "package",
    "mark_failed",
  ])

  # Per-function timeout overrides; all others default to 60 s
  worker_timeouts = {
    preflight           = 180
    dependency_map      = 300
    translate           = 180
    validate            = 300
    package             = 180
    compatibility_check = 60
    mark_failed         = 30
  }

  worker_env = {
    JOBS_TABLE         = var.jobs_table_name
    ARTIFACTS_BUCKET   = var.artifacts_bucket_name
    TRANSLATE_MODEL_ID = var.translate_model_id
    OPUS_MODEL_ID      = var.opus_model_id
    COMPAT_MODEL_ID    = var.compat_model_id
  }
}

# ---------------------------------------------------------------------------
# Shared Python layer (same source as the CRUD lambda module)
# ---------------------------------------------------------------------------

data "archive_file" "shared_layer" {
  type        = "zip"
  source_dir  = "${path.root}/../../../backend/layers/shared"
  output_path = "${path.module}/dist/shared_layer.zip"
}

resource "aws_lambda_layer_version" "shared" {
  filename                 = data.archive_file.shared_layer.output_path
  layer_name               = "${var.name_prefix}-sfn-shared"
  compatible_runtimes      = ["python3.13"]
  compatible_architectures = ["arm64"]
  source_code_hash         = data.archive_file.shared_layer.output_base64sha256
}

# ---------------------------------------------------------------------------
# Lambda archives
# ---------------------------------------------------------------------------

data "archive_file" "workers" {
  for_each    = local.worker_names
  type        = "zip"
  source_dir  = "${path.root}/../../../backend/lambdas/sfn/${each.key}"
  output_path = "${path.module}/dist/${each.key}.zip"
}

# ---------------------------------------------------------------------------
# CloudWatch log groups (pre-created to control retention)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "workers" {
  for_each          = local.worker_names
  name              = "/aws/lambda/${var.name_prefix}-sfn-${each.key}"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# IAM role for worker Lambdas
# ---------------------------------------------------------------------------

resource "aws_iam_role" "worker" {
  name = "${var.name_prefix}-sfn-worker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "worker_basic" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "worker_app" {
  name = "app-permissions"
  role = aws_iam_role.worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:PutItem"]
        Resource = [var.jobs_table_arn]
      },
      {
        Sid    = "S3Objects"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:HeadObject", "s3:ListBucket"]
        Resource = [
          var.artifacts_bucket_arn,
          "${var.artifacts_bucket_arn}/*",
        ]
      },
      {
        Sid      = "S3List"
        Effect   = "Allow"
        Action   = "s3:ListObjectsV2"
        Resource = var.artifacts_bucket_arn
      },
      {
        Sid      = "KMS"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = var.kms_key_arn
      },
      {
        # Cross-region inference profiles route to any US region internally,
        # so the IAM resource must use a wildcard region for foundation models.
        Sid    = "Bedrock"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:Converse"]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.*",
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.*",
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/global.anthropic.*",
        ]
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Worker Lambda functions
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "workers" {
  for_each = local.worker_names

  function_name    = "${var.name_prefix}-sfn-${each.key}"
  filename         = data.archive_file.workers[each.key].output_path
  source_code_hash = data.archive_file.workers[each.key].output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.13"
  architectures    = ["arm64"]
  role             = aws_iam_role.worker.arn
  layers           = [aws_lambda_layer_version.shared.arn]
  timeout          = lookup(local.worker_timeouts, each.key, 60)
  memory_size      = 512

  environment {
    variables = local.worker_env
  }

  depends_on = [aws_cloudwatch_log_group.workers]
}

# ---------------------------------------------------------------------------
# IAM role for Step Functions (invoke Lambdas + write CW logs)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "sfn" {
  name = "${var.name_prefix}-sfn-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "sfn_exec" {
  name = "sfn-exec"
  role = aws_iam_role.sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeLambdas"
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = concat(
          [for v in aws_lambda_function.workers : v.arn],
          [for v in aws_lambda_function.workers : "${v.arn}:*"],
        )
      },
      {
        # Required for Step Functions execution logging to CloudWatch
        Sid    = "CWLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# CloudWatch log group for the state machine
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/states/${var.name_prefix}-translate-job"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Step Functions state machine
# ---------------------------------------------------------------------------

resource "aws_sfn_state_machine" "translate_job" {
  name     = "${var.name_prefix}-translate-job"
  role_arn = aws_iam_role.sfn.arn
  type     = "STANDARD"

  definition = local.sfn_definition

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }
}
