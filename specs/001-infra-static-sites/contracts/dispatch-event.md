# Contract: App-repo → Infra-repo Deployment Event

**Mechanism**: GitHub `repository_dispatch` from an app-repo to the infra-repo.

**Auth**: `INFRA_REPO_DISPATCH_TOKEN` (GitHub PAT, `repo` scope on infra-repo). Referenced only as
`${{ secrets.INFRA_REPO_DISPATCH_TOKEN }}`; never logged.

## Request payload

```json
{
  "event_type": "deploy",
  "client_payload": {
    "service_name": "buyraq",
    "image_tag": "<commit-sha>",
    "domain": "buyraq.com"
  }
}
```

## Field rules

| Field | Required | Validation |
|-------|----------|------------|
| event_type | yes | Constant `deploy` |
| service_name | yes | MUST be one of: buyraq, codehelp, cosmeticpro, ddnsteltonicka, solovkadmytro, solovkaskincare |
| image_tag | yes | Non-empty; the commit SHA pushed to ECR Public |
| domain | yes | MUST be the approved domain paired with `service_name` |

## Infra-repo handling contract

1. Reject (fail fast) if `service_name` is unknown or `domain` does not match the approved pairing.
2. Run `terraform plan` — MUST exit 0.
3. Over SSH: `docker compose pull <service_name> && docker compose up -d <service_name>`.
4. Wait ~15s, then run the validation suite (see `validation-suite.md`).
5. On any failure: post a summary to workflow annotations and exit 1.
