# Contract: Post-Deploy Validation Suite

Runs in the infra-repo deploy workflow after the service is brought up. Covers all 6 domains.
Any single failure fails the workflow (exit 1) with a concise summary.

## Inputs

- The 6 approved domains and their `service_name` mapping (see `data-model.md`).
- The EC2 Elastic IP (Terraform output).
- Intended image digests from Amazon ECR Public.

## Checks

| ID | Check | Command (reference) | Pass condition |
|----|-------|---------------------|----------------|
| V1 | Terraform drift | `terraform plan -detailed-exitcode` | Exit code 0 (no changes) |
| V2 | DNS resolution | `dig +short <domain>` | Returns the EC2 Elastic IP, for all 6 |
| V3 | HTTPS health | `curl -sSf https://<domain>` | HTTP 200 + valid Let's Encrypt cert, for all 6 |
| V4 | HTTP redirect | `curl -sSI http://<domain>` | 301/308 redirect to `https://`, for all 6 |
| V5 | Image freshness | compare running digest vs ECR Public digest | Match, for each service |

## Output contract

- **All pass**: workflow exits 0; summary lists 6/6 domains healthy.
- **Any fail**: workflow exits 1; summary names each failed check and domain/service. No manual
  override is permitted (Principle VII).
