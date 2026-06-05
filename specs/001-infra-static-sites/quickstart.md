# Quickstart: Static Sites Infrastructure

A validation/run guide. Implementation details live in `tasks.md` (next phase) and the target
repositories. Do not commit real secrets — use `.env` (git-ignored) and GitHub Secrets.

## Prerequisites

- AWS account with programmatic access (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, region `us-east-1`).
- Cloudflare account managing the 6 domains (`CLOUDFLARE_API_TOKEN`, account id, email).
- Amazon ECR Public registry alias (`ECR_PUBLIC_ALIAS`).
- An S3 bucket (`AWS_BUCKET_NAME`) and a DynamoDB lock table (`AWS_TF_LOCK_TABLE`).
- Project SSH key pair in `.ssh/` (`project_key` / `project_key.pub`).
- Tools: Terraform >= 1.7, Docker + Compose, AWS CLI, `dig`, `curl`.

## One-time bootstrap

1. Create the S3 state bucket and DynamoDB lock table (once).
2. Generate the EC2 deploy key pair into `.ssh/`; add the public key to Terraform key-pair input.
3. Populate GitHub Secrets in infra-repo and app-repos per the constitution's secrets list.

## Provision infrastructure (manual / approval-gated apply)

```bash
cd infra-repo/terraform
terraform init
terraform plan      # review: only 6 site A-records + EC2/SG/keypair; NO mail-record changes
terraform apply     # manual or protected workflow only
```

Expected: one `t2.micro` running, Elastic IP attached, 6 `cloudflare_dns_record` A-records
(`proxied=false`, `ttl=60`) pointing at the EIP.

## Bring up containers (on EC2)

```bash
cd infra-repo/compose
docker compose config        # must validate
docker compose pull
docker compose up -d          # traefik + 6 nginx services
```

## End-to-end validation (proves the feature)

Run for each of the 6 domains (buyraq.com, codehelp.pp.ua, cosmeticpro.pp.ua, ddnsteltonicka.pp.ua,
solovkadmytro.pp.ua, solovkaskincare.pp.ua):

```bash
dig +short <domain>                 # → EC2 Elastic IP
curl -sSf https://<domain>          # → HTTP 200, valid Let's Encrypt cert
curl -sSI http://<domain>           # → redirect to https://
```

Terraform drift gate:

```bash
terraform plan -detailed-exitcode   # exit code 0 = zero drift
```

See `contracts/validation-suite.md` for the full pass/fail contract.

## App update flow (per app-repo)

1. Edit `index.html`, push to `main`.
2. Build workflow builds and pushes `public.ecr.aws/<alias>/<service>:<sha>` (and `latest`).
3. Workflow fires `repository_dispatch` to infra-repo (`{ service_name, image_tag, domain }`).
4. Infra-repo deploy workflow pulls that service, restarts it, and runs the validation suite.

Done when all 6 domains pass DNS + HTTPS + redirect + digest checks and Terraform shows zero drift.
