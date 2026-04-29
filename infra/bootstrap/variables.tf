variable "project" {
  description = "Project name, used as a prefix for all resources."
  type        = string
  default     = "rosetta"
}

variable "region" {
  description = "AWS region for the deployment. Single-region project."
  type        = string
  default     = "us-east-1"
}

variable "tfstate_bucket_suffix" {
  description = "Suffix appended to the tfstate bucket name to make it globally unique. Typically the AWS account ID."
  type        = string
}
