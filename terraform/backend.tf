# Remote state in S3 with native S3 state locking (use_lockfile, Terraform >= 1.11).
# No DynamoDB table is required. The bucket is created once by terraform/bootstrap.
# The bucket name is supplied at init time via partial backend config:
#
#   terraform init \
#     -backend-config="bucket=$AWS_BUCKET_NAME" \
#     -backend-config="region=$AWS_REGION"
terraform {
  backend "s3" {
    key          = "terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}
