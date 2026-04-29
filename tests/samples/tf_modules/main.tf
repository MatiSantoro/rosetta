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

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "storage" {
  source      = "./modules/storage"
  project     = var.project
  environment = var.environment
}

module "database" {
  source             = "./modules/database"
  project            = var.project
  environment        = var.environment
  log_retention_days = var.log_retention_days
}

module "lambda" {
  source             = "./modules/lambda"
  project            = var.project
  environment        = var.environment
  log_retention_days = var.log_retention_days
  jobs_table_name    = module.database.jobs_table_name
  jobs_table_arn     = module.database.jobs_table_arn
  bucket_name        = module.storage.bucket_name
  bucket_arn         = module.storage.bucket_arn
}
