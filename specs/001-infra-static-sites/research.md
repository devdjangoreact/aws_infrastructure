# Phase 0 Research: Static Sites Infrastructure

## R1. Cloudflare Terraform provider — DNS record resource

- **Decision**: Use provider `cloudflare/cloudflare ~> 5` with the `cloudflare_dns_record` resource;
  set `type = "A"`, the IP via `content`, `proxied = false`, `ttl = 60`.
- **Rationale**: In Cloudflare provider v5 the old `cloudflare_record` resource was renamed to
  `cloudflare_dns_record`, and the IP/value attribute changed from `value` to `content`. The
  constitution's wording (`cloudflare_record`, "type A, proxied=false, TTL=60") describes intent;
  the v5 resource name and `content` attribute are the correct implementation form.
- **Alternatives considered**: Provider v4 (`cloudflare_record` + `value`) — rejected to avoid
  starting on a deprecated resource; managing DNS by hand — rejected because it breaks the
  reproducibility and validation principles.

## R2. Protecting mail / non-site DNS records

- **Decision**: Declare ONLY the 6 site A-records as Terraform resources. Do not import the zone,
  do not use any "manage all records" construct, and review every `plan` for destroy/modify of
  records Terraform does not own.
- **Rationale**: Constitution Principle V forbids touching `MX`, `TXT` (SPF/DKIM/DMARC), and
  mail-related `CNAME`/`SRV`. Terraform only affects resources in state, so unmanaged records are
  safe as long as no zone-wide ownership resource is used.
- **Alternatives considered**: Full-zone management — rejected (would delete existing mail records).

## R3. TLS termination — Traefik + Let's Encrypt (ACME HTTP-01)

- **Decision**: Traefik v3 terminates TLS using an ACME HTTP-01 resolver against Let's Encrypt
  production; certs stored in `acme.json` (mode 600) on a Docker volume. HTTP entrypoint redirects
  to HTTPS globally.
- **Rationale**: HTTP-01 needs ports 80/443 reachable directly, which is why Cloudflare proxy must
  be OFF (grey cloud). Matches Principle III.
- **Alternatives considered**: DNS-01 challenge (would allow orange-cloud proxy but needs
  Cloudflare API token in Traefik and adds complexity) — rejected for Phase 1 simplicity;
  Cloudflare Origin certs — rejected because proxy is off.

## R4. Image registry — Amazon ECR Public

- **Decision**: Store all 6 images in Amazon ECR Public under `public.ecr.aws/<alias>/<service>`.
  Login for push: `aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws`.
- **Rationale**: Constitution Principle VI mandates ECR Public and forbids Docker Hub. ECR Public
  API is only in `us-east-1`, matching `AWS_REGION`. Pulls can be anonymous on the EC2 host.
- **Alternatives considered**: Docker Hub (forbidden by constitution); private ECR (adds pull-auth
  burden on the host without benefit for public static sites).

## R5. Image tagging for reproducibility

- **Decision**: Build and push two tags per app: the commit SHA and `latest`. `docker-compose.yml`
  pins the SHA tag; dispatch payload carries the SHA as `image_tag`.
- **Rationale**: Principle VI requires immutable pinning so any deployed state is reconstructible.
- **Alternatives considered**: `latest` only — rejected (not reproducible, ambiguous digests).

## R6. Deploy trigger — repository_dispatch

- **Decision**: App-repo build workflow fires a `repository_dispatch` to infra-repo with payload
  `{ service_name, image_tag, domain }` using `INFRA_REPO_DISPATCH_TOKEN` (PAT, repo scope). Infra
  deploy workflow runs on that event and on direct push to `main`.
- **Rationale**: Enforces Principles I and II — app-repos only notify; infra-repo deploys.
- **Alternatives considered**: Shared deploy workflow in each app-repo — rejected (violates
  separation); webhook server on EC2 — rejected (extra surface, not needed).

## R7. Remote state and locking

- **Decision**: S3 backend (`AWS_BUCKET_NAME`, key `terraform.tfstate`) + DynamoDB lock table
  (`AWS_TF_LOCK_TABLE`), created once via a bootstrap step.
- **Rationale**: Principle V requires remote state with locking to avoid concurrent corruption.
- **Alternatives considered**: Local state — rejected (not shareable, no locking).

## R8. CI safety — plan-only

- **Decision**: CI runs `terraform validate` + `terraform plan` only. `terraform apply` runs
  manually or via a protected, approval-gated workflow.
- **Rationale**: Principle V mandates plan-only CI; zero drift expected.
- **Alternatives considered**: Auto-apply on merge — rejected (destructive risk to live infra).

## R9. Provisioning Docker on EC2

- **Decision**: Install Docker + Compose plugin via Terraform `user_data` at first boot; an
  Elastic IP is attached so the public IP is stable across stop/start.
- **Rationale**: Principle/Standards recommend EIP to keep DNS A-records valid; user_data keeps
  provisioning reproducible.
- **Alternatives considered**: Ansible post-provision — viable but heavier for Phase 1; no EIP —
  rejected (IP churn breaks DNS).

## Resolved unknowns

All Technical Context items are resolved; no `NEEDS CLARIFICATION` markers remain.
