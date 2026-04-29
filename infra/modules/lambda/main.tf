locals {
  handler_names = toset(["create_job", "start_job", "get_job", "list_jobs", "get_download"])

  common_env = {
    JOBS_TABLE        = var.jobs_table_name
    QUOTA_TABLE       = var.usage_quota_table_name
    ARTIFACTS_BUCKET  = var.artifacts_bucket_name
    DAILY_JOB_QUOTA   = tostring(var.daily_job_quota)
    STATE_MACHINE_ARN = var.state_machine_arn
  }
}

# ---------------------------------------------------------------------------
# Shared Python layer (ddb_utils, s3_utils, response)
# ---------------------------------------------------------------------------

data "archive_file" "shared_layer" {
  type        = "zip"
  source_dir  = "${path.root}/../../../backend/layers/shared"
  output_path = "${path.module}/dist/shared_layer.zip"
}

resource "aws_lambda_layer_version" "shared" {
  filename                 = data.archive_file.shared_layer.output_path
  layer_name               = "${var.name_prefix}-shared"
  compatible_runtimes      = ["python3.13"]
  compatible_architectures = ["arm64"]
  source_code_hash         = data.archive_file.shared_layer.output_base64sha256
}

# ---------------------------------------------------------------------------
# IAM role shared by all CRUD Lambda functions
# ---------------------------------------------------------------------------

resource "aws_iam_role" "crud" {
  name = "${var.name_prefix}-crud-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "crud_basic_execution" {
  role       = aws_iam_role.crud.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "crud_app" {
  name = "app-permissions"
  role = aws_iam_role.crud.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "DynamoDB"
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:Query",
            "dynamodb:ConditionCheckItem",
          ]
          Resource = [
            var.jobs_table_arn,
            "${var.jobs_table_arn}/index/*",
            var.usage_quota_table_arn,
          ]
        },
        {
          Sid      = "S3Objects"
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject", "s3:HeadObject"]
          Resource = "${var.artifacts_bucket_arn}/*"
        },
        {
          Sid    = "KMS"
          Effect = "Allow"
          Action = ["kms:GenerateDataKey", "kms:Decrypt"]
          Resource = var.kms_key_arn
        },
      ],
      var.state_machine_arn != "" ? [{
        Sid      = "StepFunctions"
        Effect   = "Allow"
        Action   = "states:StartExecution"
        Resource = var.state_machine_arn
      }] : []
    )
  })
}

# ---------------------------------------------------------------------------
# Lambda function zip archives (one per handler directory)
# ---------------------------------------------------------------------------

data "archive_file" "handlers" {
  for_each    = local.handler_names
  type        = "zip"
  source_dir  = "${path.root}/../../../backend/lambdas/${each.key}"
  output_path = "${path.module}/dist/${each.key}.zip"
}

# ---------------------------------------------------------------------------
# CloudWatch log groups (pre-created to control retention)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "handlers" {
  for_each          = local.handler_names
  name              = "/aws/lambda/${var.name_prefix}-${each.key}"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Lambda functions
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "handlers" {
  for_each = local.handler_names

  function_name    = "${var.name_prefix}-${each.key}"
  filename         = data.archive_file.handlers[each.key].output_path
  source_code_hash = data.archive_file.handlers[each.key].output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.13"
  architectures    = ["arm64"]
  role             = aws_iam_role.crud.arn
  layers           = [aws_lambda_layer_version.shared.arn]
  timeout          = 29
  memory_size      = 256

  environment {
    variables = local.common_env
  }

  depends_on = [aws_cloudwatch_log_group.handlers]
}
