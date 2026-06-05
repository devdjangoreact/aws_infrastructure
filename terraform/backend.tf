# Remote state in S3 with DynamoDB locking.
# Bucket and lock table are supplied at init time via partial backend config so no
# environment-specific values are hardcoded:
#
#   terraform init \
#     -backend-config="bucket=$AWS_BUCKET_NAME" \
#     -backend-config="dynamodb_table=$AWS_TF_LOCK_TABLE" \
#     -backend-config="region=$AWS_REGION"
terraform {
  backend "s3" {
    key     = "terraform.tfstate"
    encrypt = true
  }
}
