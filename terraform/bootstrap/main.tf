# One-time bootstrap: creates the S3 bucket used for the main config's remote state.
# Uses LOCAL state (chicken-and-egg: a backend bucket cannot create itself).
# Run once:
#   cd terraform/bootstrap
#   terraform init
#   terraform apply -var="bucket_name=$AWS_BUCKET_NAME"

terraform {
  required_version = ">= 1.11"
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

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "bucket_name" {
  description = "Name of the S3 bucket for Terraform remote state (AWS_BUCKET_NAME)."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_name)) && !can(regex("_", var.bucket_name))
    error_message = "S3 bucket names must be 3-63 chars, lowercase letters/numbers/dots/hyphens only, and cannot contain underscores."
  }
}

resource "aws_s3_bucket" "state" {
  #checkov:skip=CKV_AWS_18:This bootstrap bucket stores Terraform state only; versioning and encryption are enabled.
  #checkov:skip=CKV_AWS_144:Cross-region replication is unnecessary for this single-region free-tier state bucket.
  #checkov:skip=CKV_AWS_145:AES256 server-side encryption is sufficient for this Terraform state bucket.
  #checkov:skip=CKV2_AWS_61:Lifecycle cleanup is intentionally omitted so Terraform state history remains available.
  #checkov:skip=CKV2_AWS_62:State object changes are managed by Terraform locking; event notifications are not needed.
  bucket = var.bucket_name

  # Allow `terraform destroy` to remove the bucket even if it still holds state versions.
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

#trivy:ignore:AVD-AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "bucket_name" {
  value = aws_s3_bucket.state.id
}
