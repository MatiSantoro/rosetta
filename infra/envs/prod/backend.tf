terraform {
  backend "s3" {
    bucket       = "rosetta-prod-tfstate-454634138593"
    key          = "envs/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
