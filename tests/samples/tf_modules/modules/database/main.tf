resource "aws_dynamodb_table" "jobs" {
  name         = "${var.project}-${var.environment}-jobs"
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
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "updatedAt"
    type = "S"
  }

  global_secondary_index {
    name            = "status-updatedAt-index"
    hash_key        = "status"
    range_key       = "updatedAt"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "quota" {
  name         = "${var.project}-${var.environment}-quota"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "date"

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
}
