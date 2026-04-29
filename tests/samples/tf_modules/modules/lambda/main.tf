resource "aws_iam_role" "processor" {
  name = "${var.project}-${var.environment}-processor"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "processor_basic" {
  role       = aws_iam_role.processor.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "processor_app" {
  name = "app-permissions"
  role = aws_iam_role.processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
        Resource = [
          var.jobs_table_arn,
          "${var.jobs_table_arn}/index/*",
        ]
      },
      {
        Sid      = "S3"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:HeadObject"]
        Resource = "${var.bucket_arn}/*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "processor" {
  name              = "/aws/lambda/${var.project}-${var.environment}-processor"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "processor" {
  function_name = "${var.project}-${var.environment}-processor"
  runtime       = "python3.13"
  handler       = "handler.handler"
  role          = aws_iam_role.processor.arn
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]
  filename      = "placeholder.zip"

  environment {
    variables = {
      JOBS_TABLE  = var.jobs_table_name
      DATA_BUCKET = var.bucket_name
      ENVIRONMENT = var.environment
    }
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  depends_on = [aws_cloudwatch_log_group.processor]
}
