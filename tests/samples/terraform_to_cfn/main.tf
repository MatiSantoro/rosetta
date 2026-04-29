terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

# ── Storage ──────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "data" {
  bucket = "sample-data-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "jobs" {
  name         = "jobs-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "jobId"

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "jobId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}

# ── IAM ──────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "processor" {
  name = "processor-role-${var.environment}"

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

resource "aws_iam_role_policy" "processor_data" {
  name = "data-access"
  role = aws_iam_role.processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DynamoDB"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
        Resource = aws_dynamodb_table.jobs.arn
      },
      {
        Sid      = "S3"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.data.arn}/*"
      },
    ]
  })
}

# ── Compute ───────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "processor" {
  name              = "/aws/lambda/processor-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "processor" {
  function_name = "processor-${var.environment}"
  runtime       = "python3.13"
  handler       = "handler.handler"
  role          = aws_iam_role.processor.arn
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]
  filename      = "handler.zip"

  environment {
    variables = {
      JOBS_TABLE  = aws_dynamodb_table.jobs.name
      DATA_BUCKET = aws_s3_bucket.data.id
      ENVIRONMENT = var.environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.processor]
}
