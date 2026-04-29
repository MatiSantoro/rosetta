output "tfstate_bucket" {
  description = "Name of the S3 bucket that holds Terraform remote state. Use this in envs/*/backend.tf."
  value       = aws_s3_bucket.tfstate.id
}
