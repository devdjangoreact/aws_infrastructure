# GitHub Secrets Matrix

All sensitive values are stored as GitHub Actions secrets and referenced only as
`${{ secrets.NAME }}`. They are never echoed or logged. Real values live only in the local
git-ignored `.env` and in GitHub; see `.env.example` for the variable list.

## infra-repo secrets

| Secret | Purpose |
|--------|---------|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account for DNS site A-records |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token (DNS edit, scoped to the managed zones) |
| `CLOUDFLARE_EMAIL` | Cloudflare account email |
| `AWS_ACCESS_KEY_ID` | AWS credentials (EC2, S3 state, ECR Public) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_REGION` | `us-east-1` |
| `AWS_BUCKET_NAME` | S3 bucket for Terraform remote state (native S3 locking, no DynamoDB) |
| `ECR_PUBLIC_ALIAS` | Amazon ECR Public registry alias |
| `EC2_HOST` | EC2 host/IP for SSH deploy |
| `EC2_SSH_PRIVATE_KEY` | Deploy private key material (from `.ssh/project_key`) |

## app-repo secrets (each of the 6)

| Secret | Purpose |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | ECR Public login for image push |
| `AWS_SECRET_ACCESS_KEY` | ECR Public login for image push |
| `ECR_PUBLIC_ALIAS` | Target registry alias for the pushed image |
| `INFRA_REPO_DISPATCH_TOKEN` | GitHub PAT (`repo` scope) to dispatch the deploy event |

## Notes

- The deploy key pair lives in `.ssh/` (`project_key` / `project_key.pub`); the public key is added
  to the EC2 `authorized_keys`, and the private key is provided only via `EC2_SSH_PRIVATE_KEY`.
- App-repos never receive AWS deploy/SSH or Cloudflare credentials beyond ECR Public push access.
