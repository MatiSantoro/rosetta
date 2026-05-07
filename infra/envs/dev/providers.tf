provider "aws" {
  region  = var.region
  profile = "rosetta-prod"   # same account (454634138593) as prod, isolated by name_prefix

  default_tags {
    tags = {
      Project   = var.project
      Env       = var.env
      ManagedBy = "terraform"
    }
  }
}
