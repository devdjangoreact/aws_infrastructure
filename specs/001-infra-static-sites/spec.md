# Feature Specification: Static Sites Infrastructure

**Feature Branch**: `001-infra-static-sites`

**Created**: 2026-06-05

**Status**: Draft

**Input**: User description: "Create reproducible AWS infrastructure for 6 containerized static websites on one free-tier EC2 instance, routed by Traefik, with Cloudflare DNS, Amazon ECR Public images, GitHub Actions CI/CD across 7 repositories, and full validation gates."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publish six HTTPS static sites (Priority: P1)

As the infrastructure owner, I need all 6 domains to serve their own static website over HTTPS from one shared server so the project can run within the free-tier footprint while keeping each site independently addressable.

**Why this priority**: This is the core business outcome. Without reachable HTTPS sites, no later automation or validation provides value.

**Independent Test**: Can be tested by visiting each managed domain and confirming that it returns the correct static page over HTTPS and redirects HTTP requests to HTTPS.

**Acceptance Scenarios**:

1. **Given** the infrastructure is provisioned, **When** a visitor opens `https://buyraq.com`, **Then** the page for the `buyraq.com` site is returned successfully.
2. **Given** the infrastructure is provisioned, **When** a visitor opens each of the 6 managed domains over HTTP, **Then** every request redirects to HTTPS.
3. **Given** all sites are deployed, **When** one site is requested, **Then** content from another site is not returned.

---

### User Story 2 - Deploy app changes through repository ownership boundaries (Priority: P2)

As an app-repo maintainer, I need a push to my repository's `main` branch to publish only my site's new image and notify the infra-repo so I can update my site without receiving deployment authority.

**Why this priority**: This keeps repository responsibilities separated while allowing each site to update independently.

**Independent Test**: Can be tested by pushing a content change to one app-repo and confirming only that service is refreshed through the infra-repo workflow.

**Acceptance Scenarios**:

1. **Given** an app-repo receives a push to `main`, **When** its build workflow completes, **Then** a new image is published to Amazon ECR Public and a dispatch event identifies `service_name`, `image_tag`, and `domain`.
2. **Given** the infra-repo receives the dispatch event, **When** deployment runs, **Then** only the changed service is refreshed and the other 5 services remain available.

---

### User Story 3 - Validate infrastructure health on every deploy (Priority: P3)

As the infrastructure owner, I need every deploy and direct infra change to prove that DNS, HTTPS, and running image state are correct across all 6 domains before the workflow is considered successful.

**Why this priority**: The system must be trustworthy after changes and must fail loudly when production health is not correct.

**Independent Test**: Can be tested by triggering an infra-repo workflow and confirming that DNS, HTTPS, image freshness, and infrastructure drift checks are executed and reported.

**Acceptance Scenarios**:

1. **Given** all 6 domains are expected to be live, **When** validation runs, **Then** every domain resolves to the active server IP.
2. **Given** all 6 domains are expected to be live, **When** validation runs, **Then** every HTTPS endpoint returns a successful response with a valid certificate.
3. **Given** a validation check fails, **When** the workflow completes, **Then** the workflow is marked failed and includes a concise failure summary.

---

### User Story 4 - Preserve existing domain services (Priority: P4)

As a domain owner, I need site DNS automation to avoid modifying mail and other existing records so website deployment cannot break email or unrelated services.

**Why this priority**: The project manages websites only; breaking mail records would be a severe unintended side effect.

**Independent Test**: Can be tested by reviewing the infrastructure change plan and confirming it only creates or updates the approved site A-records.

**Acceptance Scenarios**:

1. **Given** a managed Cloudflare zone has existing mail records, **When** infrastructure changes are planned, **Then** mail and non-site records are not created, modified, or deleted.
2. **Given** a plan shows a non-site DNS record change, **When** the workflow evaluates the plan, **Then** the change is blocked before apply.

### Edge Cases

- A managed domain already has existing `MX`, `TXT`, `CNAME`, or `SRV` records for mail or other services.
- The shared server IP changes before DNS records are updated.
- A certificate cannot be issued because a domain is proxied or the HTTP challenge cannot reach the server.
- One app image is missing, stale, or unavailable in Amazon ECR Public.
- A single app-repo dispatch payload references an unknown service or a domain outside the approved list.
- The server is reachable over SSH but one or more sites fail HTTPS validation.
- Terraform detects drift or plans changes outside the approved site records.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST manage exactly 6 static websites, one per approved domain: `buyraq.com`, `codehelp.pp.ua`, `cosmeticpro.pp.ua`, `ddnsteltonicka.pp.ua`, `solovkadmytro.pp.ua`, and `solovkaskincare.pp.ua`.
- **FR-002**: Each managed domain MUST serve only its own static website content.
- **FR-003**: Each managed domain MUST be reachable over HTTPS with a valid certificate.
- **FR-004**: HTTP requests to every managed domain MUST redirect to HTTPS.
- **FR-005**: All 6 managed domains MUST resolve to the same active server IP.
- **FR-006**: Domain automation MUST manage only the approved site A-records and MUST NOT create, update, or delete mail or non-site DNS records.
- **FR-007**: The deployment authority repository MUST contain all deployment, routing, DNS, and infrastructure logic.
- **FR-008**: The 6 application repositories MUST build and publish their own website image and MUST NOT contain deployment, infrastructure, SSH, or cloud credential logic.
- **FR-009**: A push or merge to `main` in any app-repo MUST produce a publishable image for that app.
- **FR-010**: A push or merge to `main` in any app-repo MUST notify the infra-repo with the changed service name, image tag, and domain.
- **FR-011**: The infra-repo MUST refresh the changed service when it receives a valid app dispatch event.
- **FR-012**: The infra-repo MUST run the full validation suite after each deploy.
- **FR-013**: The infra-repo MUST run validation on direct pushes to its own `main` branch.
- **FR-014**: The infra-repo deployment workflow MUST run only from either a direct push/merge to `main` in infra-repo or a `repository_dispatch` sent after a push/merge to `main` in one of the 6 app-repos.
- **FR-015**: Validation MUST include DNS resolution checks for all 6 managed domains.
- **FR-016**: Validation MUST include HTTPS health checks for all 6 managed domains.
- **FR-017**: Validation MUST confirm that each running service uses the intended image digest from Amazon ECR Public.
- **FR-018**: Validation MUST fail the workflow if any DNS, HTTPS, image freshness, or infrastructure drift check fails.
- **FR-019**: The infrastructure state check MUST detect unexpected drift before deployment is treated as successful.
- **FR-020**: Secrets, tokens, private keys, credentials, and live sensitive values MUST NOT be committed to any repository.
- **FR-021**: The project MUST provide a sanitized environment example that documents required variables without exposing real values.

### Key Entities

- **Managed Domain**: One approved public domain that maps to one static website and one app-repo.
- **Static Site Service**: The deployable unit for a single domain, including the published image reference and expected runtime health.
- **App Repository**: A build-only repository responsible for one static site image and dispatch notification.
- **Infra Repository**: The deployment authority repository responsible for infrastructure, routing, DNS site records, deployment, and validation.
- **Deployment Event**: A notification from an app-repo to the infra-repo containing the changed service name, image tag, and domain.
- **Validation Result**: The recorded outcome of DNS, HTTPS, image freshness, and drift checks for a deployment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 6 managed domains return a successful HTTPS response during validation.
- **SC-002**: All 6 managed domains redirect HTTP requests to HTTPS during validation.
- **SC-003**: All 6 managed domains resolve to the active server IP during validation.
- **SC-004**: A content change pushed to one app-repo reaches the corresponding public site after the deploy workflow completes.
- **SC-005**: A deploy workflow that encounters any failed DNS, HTTPS, image freshness, or drift check exits with a failed status and a visible failure summary.
- **SC-006**: Infrastructure validation reports zero unexpected drift before a deployment is marked successful.
- **SC-007**: No mail or non-site DNS records are modified by infrastructure automation.
- **SC-008**: No real secret values are present in tracked repository files.

## Assumptions

- The project has one infra-repo and 6 app-repos, each app-repo mapped to exactly one managed domain.
- The approved domain-to-app mapping is one-to-one and uses the 6 domains listed in FR-001.
- Existing mail and non-site DNS records may already exist and must remain manually managed in Cloudflare.
- Amazon ECR Public is the authoritative image registry for all site images.
- The shared server is intended for minimal static HTML sites, not dynamic applications or databases.
- Production deployment is allowed only through infra-repo workflows or explicitly approved manual infrastructure apply operations.
