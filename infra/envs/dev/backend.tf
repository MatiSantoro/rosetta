terraform {
  backend "s3" {
    # NOTE: replace CHANGE_ME with your AWS account ID after running
    # `infra/bootstrap` (it creates rosetta-tfstate-<ACCOUNT_ID>).
    # Or use the sed command in the README to do it automatically.
    bucket       = "rosetta-tfstate-239248123204"
    key          = "envs/dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true  # S3-native locking (Terraform >= 1.10); no DynamoDB needed
  }
}
