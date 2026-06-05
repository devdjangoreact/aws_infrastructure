# Static Sites Infrastructure (infra-repo)

Reproducible, automated infrastructure that runs 6 containerized static websites on a single AWS
free-tier EC2 instance, routed by Traefik over HTTPS, with DNS in Cloudflare and images in Amazon
ECR Public. CI/CD is split across 7 repositories.

## Repository roles

- **infra-repo (this repo)** — deployment authority. Owns Terraform, Docker Compose, Traefik
  config, deploy workflow, and the validation suite.
- **app-repo-1..6** — build authority. Each owns one domain, one `Dockerfile`, one `index.html`,
  and a build workflow. App-repos build, push to ECR Public, and notify infra-repo. They never
  deploy. A starter template is in `templates/app-repo/`.

## Layout

```text
terraform/                 # EC2, security group, key pair, Elastic IP, Cloudflare site A-records
compose/
  docker-compose.yml       # Traefik + 6 nginx services (SHA-pinned via *_TAG env)
  traefik/traefik.yml      # entrypoints, ACME (Let's Encrypt HTTP-01), dashboard off
scripts/
  deploy.sh                # pull + up -d for one changed service
  validate.sh              # DNS + HTTPS + redirect + digest checks for all 6 domains
.github/workflows/deploy.yml  # repository_dispatch (from app-repos) + push/merge to main
templates/app-repo/        # starter for each of the 6 app-repos
docs/                      # domain map, secrets matrix, runbook
specs/001-infra-static-sites/  # spec, plan, research, contracts, tasks
```

## Managed domains

`buyraq.com`, `codehelp.pp.ua`, `cosmeticpro.pp.ua`, `ddnsteltonicka.pp.ua`,
`solovkadmytro.pp.ua`, `solovkaskincare.pp.ua` — all DNS-only (Cloudflare grey cloud), all
pointing at the same EC2 Elastic IP.

## Deploy triggers

The infra-repo deploy workflow runs only from:

1. a push/merge to `main` in infra-repo, or
2. a `repository_dispatch` sent after a push/merge to `main` in one of the 6 app-repos.

## Usage

See `docs/runbook.md` for bring-up and rollback, `docs/github-secrets.md` for the secret matrix,
and `specs/001-infra-static-sites/quickstart.md` for end-to-end validation. Secrets are stored in
GitHub and the local git-ignored `.env`; never commit real secrets (`.env.example` lists the keys).

## Definition of done (Phase 1)

1. EC2 running and reachable.
2. All 6 domains resolve to the EC2 IP in Cloudflare DNS.
3. All 6 containers serve their `index.html` over HTTPS with a valid Let's Encrypt certificate.
4. HTTP redirects to HTTPS on every domain.
5. A push to any app-repo `main` triggers the infra-repo deploy workflow and passes all 6 checks.
6. `terraform plan` in CI shows zero drift.
7. All secrets are stored in GitHub, not in any repository file.
