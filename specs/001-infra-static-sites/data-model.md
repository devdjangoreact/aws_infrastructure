# Phase 1 Data Model: Static Sites Infrastructure

This project has no application database. The "entities" are infrastructure and pipeline objects.

## Entity: Managed Domain

| Field | Type | Rules |
|-------|------|-------|
| domain | string (FQDN) | One of the 6 approved domains; unique |
| service_name | string | Maps 1:1 to a domain and an app-repo |
| dns_record_type | enum | Always `A` |
| dns_proxied | bool | Always `false` (Cloudflare grey cloud) |
| dns_ttl | number | `60` |
| target_ip | string (IPv4) | The EC2 Elastic IP; shared by all 6 domains |

**Approved set** (domain → service_name):

| domain | service_name |
|--------|--------------|
| buyraq.com | buyraq |
| codehelp.pp.ua | codehelp |
| cosmeticpro.pp.ua | cosmeticpro |
| ddnsteltonicka.pp.ua | ddnsteltonicka |
| solovkadmytro.pp.ua | solovkadmytro |
| solovkaskincare.pp.ua | solovkaskincare |

## Entity: Static Site Service

| Field | Type | Rules |
|-------|------|-------|
| service_name | string | Matches Managed Domain |
| image_ref | string | `public.ecr.aws/<alias>/<service_name>` |
| image_tag | string | Commit SHA (immutable); `latest` also published |
| running_digest | string | Must equal intended ECR Public digest after deploy |
| traefik_router_rule | string | `Host(<domain>)`, entrypoint `websecure`, TLS `letsencrypt` |
| host_ports | none | Containers expose NO host ports (Traefik network only) |

**State transitions**: `built` → `pushed (ECR Public)` → `dispatched` → `pulled on EC2` →
`running` → `validated`. A failed validation leaves the previous running container in place.

## Entity: App Repository

| Field | Type | Rules |
|-------|------|-------|
| repo | string | One of app-repo-1..6 |
| owns_domain | string | Exactly one Managed Domain |
| contents | set | `Dockerfile`, `index.html`, build workflow only |
| forbidden | set | No Terraform, deploy logic, SSH keys, or cloud creds |

## Entity: Infra Repository

| Field | Type | Rules |
|-------|------|-------|
| repo | string | Single deployment authority |
| contents | set | Terraform, docker-compose, Traefik config, deploy workflow, scripts |
| state_backend | string | S3 bucket + key `terraform.tfstate` |
| state_lock | string | DynamoDB table |

## Entity: Deployment Event (repository_dispatch payload)

| Field | Type | Rules |
|-------|------|-------|
| event_type | string | e.g. `deploy` |
| service_name | string | Must be in the approved set |
| image_tag | string | Commit SHA that was pushed |
| domain | string | Must match `service_name`'s approved domain |

## Entity: Validation Result

| Field | Type | Rules |
|-------|------|-------|
| terraform_plan | enum | `zero-drift` required to pass |
| dns_check | map<domain,bool> | All 6 must resolve to EC2 IP |
| https_check | map<domain,bool> | All 6 must return 200 with valid cert |
| digest_check | map<service,bool> | All running digests match ECR Public |
| outcome | enum | `pass` → exit 0; any failure → `fail` + summary + exit 1 |
