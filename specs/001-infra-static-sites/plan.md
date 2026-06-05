# Implementation Plan: Static Sites Infrastructure

**Branch**: `001-infra-static-sites` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-infra-static-sites/spec.md`

## Summary

Provision one AWS free-tier EC2 instance that runs Traefik plus 6 `nginx:alpine` containers, each
serving a single static site on its own domain over HTTPS (Let's Encrypt). DNS site A-records are
managed in Cloudflare (DNS-only). Images live in Amazon ECR Public. A 7-repository GitHub Actions
flow separates build authority (6 app-repos) from deployment authority (infra-repo): app-repos
build, push, and dispatch after push/merge to `main`; infra-repo deploys over SSH from either that
`repository_dispatch` event or a push/merge to infra-repo `main`, then runs DNS/HTTPS/digest/drift
validation gates.

## Technical Context

**Language/Version**: HCL (Terraform >= 1.7), YAML (Docker Compose, GitHub Actions), Bash (deploy
and validation scripts), static HTML/CSS

**Primary Dependencies**: Terraform (AWS provider ~> 5, Cloudflare provider ~> 5), Docker + Docker
Compose, Traefik v3, `nginx:alpine`, Let's Encrypt (ACME HTTP-01), Amazon ECR Public, GitHub Actions

**Storage**: Terraform remote state in S3 (`AWS_BUCKET_NAME`, key `terraform.tfstate`); state lock
in DynamoDB; ACME certificate store in a Docker volume (`acme.json`, mode 600); no application
database

**Testing**: `terraform validate` + `terraform plan`; `docker compose config`; post-deploy
validation suite (DNS `dig`, HTTPS `curl`, ECR Public image digest match)

**Target Platform**: Ubuntu 22.04 LTS on AWS EC2 `t2.micro` (`us-east-1`)

**Project Type**: Infrastructure-as-code, multi-repository (1 infra-repo + 6 app-repos)

**Performance Goals**: Single small instance hosting 6 minimal static sites; all 6 HTTPS endpoints
return 200 within the post-deploy validation window

**Constraints**: Free-tier (`t2.micro`); Traefik sole ingress on 80/443; Cloudflare proxy OFF;
Terraform manages only site A-records (mail/non-site records untouched); no secrets in any repo

**Scale/Scope**: 6 domains, 6 containers, 1 server, 7 repositories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Plan compliance |
|---|-----------|-----------------|
| I | Repository Responsibility Separation | app-repos: Dockerfile/index.html/build workflow only; infra-repo owns all deploy/Terraform/Traefik. PASS |
| II | Single Source of Deployment Truth | compose, Terraform, Traefik config only in infra-repo; deploy only from infra-repo; dispatch carries `service_name`,`image_tag`,`domain`. PASS |
| III | Domain-Isolated Single-Server Routing | Traefik sole 80/443 ingress, HTTPS redirect at proxy, per-container labels, Cloudflare DNS-only, `acme.json` 600, dashboard off. PASS |
| IV | Secrets Never Touch Source Control | GitHub Secrets only; `.gitignore` excludes `.env`,`.ssh/`,`*.pem`,`*.key`,`acme.json`,`terraform.tfvars`,`.terraform/`; dedicated deploy key. PASS |
| V | Infrastructure as Code, Plan-Only in CI | Terraform manages EC2/SG/keypair/site A-records; S3+DynamoDB state; CI plan-only; apply gated; site A-records only (no mail records). PASS |
| VI | Reproducible, Pinned Containers | images in ECR Public; compose pinned to commit-SHA tag; `docker compose config` validated. PASS |
| VII | Automated Validation Gates | deploy runs `terraform plan` + DNS + HTTPS + digest checks across 6 domains; fail = exit 1. PASS |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-infra-static-sites/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── dispatch-event.md
│   └── validation-suite.md
└── checklists/
    └── requirements.md  # From /speckit-specify
```

### Source Code (target repositories)

This feature spans 7 repositories. The infra-repo is the primary deliverable of this plan; the
6 app-repos share one minimal layout.

```text
# infra-repo (deployment authority)
infra-repo/
├── terraform/
│   ├── main.tf            # EC2, security group, key pair
│   ├── dns.tf             # cloudflare_dns_record (A) for the 6 site domains only
│   ├── variables.tf       # all sensitive = true; no hardcoded secrets/IPs
│   ├── outputs.tf         # instance public IP
│   ├── providers.tf       # aws ~>5, cloudflare ~>5
│   └── backend.tf         # S3 state + DynamoDB lock
├── compose/
│   ├── docker-compose.yml # traefik + 6 nginx services (SHA-pinned images)
│   └── traefik/
│       └── traefik.yml    # entrypoints web:80/websecure:443, ACME resolver
├── scripts/
│   ├── deploy.sh          # ssh pull + up -d for changed service
│   └── validate.sh        # DNS + HTTPS + digest checks for all 6 domains
└── .github/workflows/
    └── deploy.yml         # repository_dispatch from app-repos + push/merge to infra main

# app-repo-N (build authority, x6)
app-repo-N/
├── Dockerfile             # FROM nginx:alpine; COPY index.html
├── index.html             # minimal static site
└── .github/workflows/
    └── build.yml          # on push/merge to main: build -> ECR Public push -> dispatch infra-repo
```

**Structure Decision**: Multi-repo IaC. This repository holds the infra-repo content (Terraform,
compose, Traefik, scripts, deploy workflow). App-repos are generated/maintained separately and
documented here as a shared template, since they contain no deployment logic.

## Complexity Tracking

> No constitution violations; this section is intentionally empty.
