# Runbook

Operational guide for the static sites infrastructure. See `specs/001-infra-static-sites/` for the
full spec, plan, and tasks.

## First-run (manual) bring-up on EC2

```bash
cd compose
docker compose config        # must validate
docker compose pull
docker compose up -d          # traefik + 6 nginx services
```

Traefik obtains Let's Encrypt certificates on first request per domain. Allow a minute for ACME.

## DNS safety checklist (review every terraform plan)

- [ ] Plan creates/updates ONLY the 6 approved site A-records.
- [ ] No `MX`, `TXT` (SPF/DKIM/DMARC), mail `CNAME`/`SRV`, or other record is created/modified/deleted.
- [ ] No resource takes ownership of an entire zone.
- [ ] Any non-site DNS change in the plan blocks apply (treat as failure).

## Validation suite

Run `scripts/validate.sh` (also executed by the deploy workflow). It checks, for all 6 domains:
DNS resolution, HTTPS health, HTTP→HTTPS redirect, and running image digest vs ECR Public. See
`specs/001-infra-static-sites/contracts/validation-suite.md`.

## Failed validation handling

- The deploy workflow exits 1 and prints a failure summary per failed check/domain.
- A failed deploy leaves the previous running container in place.
- Investigate, fix, and re-run the workflow. Do not mark a red gate green manually.

## Rollback

Pin the previous commit-SHA image tag for the affected service in `compose/docker-compose.yml`,
then re-run `docker compose pull <service> && docker compose up -d <service>` via the deploy flow.
