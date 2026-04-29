data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# KMS key used for at-rest encryption of artifacts and DDB tables.
# ---------------------------------------------------------------------------

resource "aws_kms_key" "this" {
  description             = "${var.name_prefix} artifacts and DDB encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name_prefix}"
  target_key_id = aws_kms_key.this.key_id
}

# ---------------------------------------------------------------------------
# DynamoDB: Jobs
# Partitioned by userId; sort by jobId. Each user only sees their own rows.
# A GSI on (status, updatedAt) supports operational dashboards.
# ---------------------------------------------------------------------------

resource "aws_dynamodb_table" "jobs" {
  name         = "${var.name_prefix}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "jobId" # deprecated in v6 but key_schema is only valid inside GSI/LSI blocks

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "jobId"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "updatedAt"
    type = "S"
  }

  global_secondary_index {
    name = "status-updatedAt-index"
    key_schema {
      attribute_name = "status"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "updatedAt"
      key_type       = "RANGE"
    }
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.this.arn
  }
}

# ---------------------------------------------------------------------------
# DynamoDB: UsageQuota
# Counts jobs per user per day for the hard rate limit. Auto-expires after
# the retention window; the per-day counter is incremented atomically with a
# conditional update enforcing the cap.
# ---------------------------------------------------------------------------

resource "aws_dynamodb_table" "usage_quota" {
  name         = "${var.name_prefix}-usage-quota"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "date" # deprecated in v6 but key_schema is only valid inside GSI/LSI blocks

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "date"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.this.arn
  }
}

# ---------------------------------------------------------------------------
# S3: artifacts bucket (inputs/, staging/, outputs/)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.name_prefix}-artifacts-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-inputs"
    status = "Enabled"
    filter { prefix = "inputs/" }
    expiration { days = var.artifacts_retention_days }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }

  rule {
    id     = "expire-staging"
    status = "Enabled"
    filter { prefix = "staging/" }
    expiration { days = var.artifacts_retention_days }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }

  rule {
    id     = "expire-outputs"
    status = "Enabled"
    filter { prefix = "outputs/" }
    expiration { days = var.artifacts_retention_days }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_s3_bucket_cors_configuration" "artifacts" {
  count = length(var.cors_allowed_origins) > 0 ? 1 : 0

  bucket = aws_s3_bucket.artifacts.id

  cors_rule {
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = var.cors_allowed_origins
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
