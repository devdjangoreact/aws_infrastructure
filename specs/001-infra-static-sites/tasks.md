# Tasks: Static Sites Infrastructure

**Input**: Design documents from `/specs/001-infra-static-sites/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No standalone test suite is generated in this task list. Validation is implemented as
deploy-time checks required by the constitution and quickstart.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated
independently where possible.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish repository layout, shared configuration, and safe defaults.

- [X] T001 Create infra-repo directory layout in `terraform/`, `compose/traefik/`, `scripts/`, and `.github/workflows/`
- [X] T002 [P] Add shared domain/service map documentation in `docs/domain-service-map.md`
- [X] T003 [P] Add non-secret environment reference updates in `.env.example`
- [X] T004 [P] Add repository hygiene rules in `.gitignore` for `.env`, `.ssh/`, `*.pem`, `*.key`, `acme.json`, `terraform.tfvars`, and `.terraform/`
- [X] T005 Add GitHub Actions environment variable naming notes in `docs/github-secrets.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core IaC, image, and deploy foundations that all user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create Terraform provider and backend definitions in `terraform/providers.tf` and `terraform/backend.tf`
- [X] T007 Create Terraform input variables with sensitive flags in `terraform/variables.tf`
- [X] T008 Create Terraform locals for the 6 approved domain/service mappings in `terraform/locals.tf`
- [X] T009 Create EC2, Elastic IP, security group, and key pair resources in `terraform/main.tf`
- [X] T010 Create Terraform outputs for EC2 public IP and Elastic IP in `terraform/outputs.tf`
- [X] T011 Create Cloudflare site A-record resources only in `terraform/dns.tf` using `cloudflare_dns_record`
- [X] T012 Add Terraform user_data bootstrap for Docker and Compose in `terraform/user_data.sh`
- [X] T013 Create Traefik static config in `compose/traefik/traefik.yml`
- [X] T014 Create baseline Docker Compose services for Traefik and all 6 sites in `compose/docker-compose.yml`
- [X] T015 Create deployment helper script in `scripts/deploy.sh`
- [X] T016 Create validation helper script skeleton in `scripts/validate.sh`
- [X] T017 Create infra deploy workflow skeleton in `.github/workflows/deploy.yml`

**Checkpoint**: Foundation ready - Terraform, Compose, Traefik, deploy, and validation files exist.

---

## Phase 3: User Story 1 - Publish six HTTPS static sites (Priority: P1) MVP

**Goal**: All 6 approved domains serve their own static site over HTTPS from one shared EC2 server.

**Independent Test**: Visit each managed domain over HTTPS and confirm the correct page is returned;
visit each over HTTP and confirm HTTPS redirect.

### Implementation for User Story 1

- [X] T018 [P] [US1] Add `buyraq` service labels and ECR Public image reference in `compose/docker-compose.yml`
- [X] T019 [P] [US1] Add `codehelp` service labels and ECR Public image reference in `compose/docker-compose.yml`
- [X] T020 [P] [US1] Add `cosmeticpro` service labels and ECR Public image reference in `compose/docker-compose.yml`
- [X] T021 [P] [US1] Add `ddnsteltonicka` service labels and ECR Public image reference in `compose/docker-compose.yml`
- [X] T022 [P] [US1] Add `solovkadmytro` service labels and ECR Public image reference in `compose/docker-compose.yml`
- [X] T023 [P] [US1] Add `solovkaskincare` service labels and ECR Public image reference in `compose/docker-compose.yml`
- [X] T024 [US1] Configure shared Docker network and prevent host port exposure for app services in `compose/docker-compose.yml`
- [X] T025 [US1] Configure Traefik HTTP-to-HTTPS redirect and ACME resolver in `compose/traefik/traefik.yml`
- [X] T026 [US1] Document manual first-run Compose commands in `docs/runbook.md`
- [X] T027 [US1] Add quick validation commands for DNS, HTTPS, and HTTP redirect in `scripts/validate.sh`

**Checkpoint**: User Story 1 is independently testable via DNS, HTTPS, and redirect checks.

---

## Phase 4: User Story 2 - Deploy app changes through repository ownership boundaries (Priority: P2)

**Goal**: A push/merge to `main` in any app-repo builds one image, pushes it to ECR Public, and
notifies infra-repo without granting app-repos deployment authority.

**Independent Test**: Push a content change to one app-repo; confirm only the matching service is
pulled and refreshed by infra-repo.

### Implementation for User Story 2

- [X] T028 [P] [US2] Create app-repo workflow template in `templates/app-repo/.github/workflows/build.yml`
- [X] T029 [P] [US2] Create app-repo Dockerfile template in `templates/app-repo/Dockerfile`
- [X] T030 [P] [US2] Create app-repo static page template in `templates/app-repo/index.html`
- [X] T031 [US2] Add ECR Public login and push steps to `templates/app-repo/.github/workflows/build.yml`
- [X] T032 [US2] Add commit-SHA and `latest` image tagging to `templates/app-repo/.github/workflows/build.yml`
- [X] T033 [US2] Add repository_dispatch payload to `templates/app-repo/.github/workflows/build.yml`
- [X] T034 [US2] Add dispatch event validation for `service_name`, `image_tag`, and `domain` in `.github/workflows/deploy.yml`
- [X] T035 [US2] Implement changed-service pull and restart flow in `scripts/deploy.sh`
- [X] T036 [US2] Document app-repo secret requirements in `docs/github-secrets.md`

**Checkpoint**: User Story 2 is independently testable by triggering a dispatch for one service.

---

## Phase 5: User Story 3 - Validate infrastructure health on every deploy (Priority: P3)

**Goal**: Every deploy and direct infra change proves DNS, HTTPS, redirect, image freshness, and
drift status before the workflow succeeds.

**Independent Test**: Trigger the infra workflow and confirm all validation checks run; intentionally
break one check in a safe branch and confirm workflow failure.

### Implementation for User Story 3

- [X] T037 [P] [US3] Implement Terraform validate and plan steps in `.github/workflows/deploy.yml`
- [X] T038 [P] [US3] Implement DNS resolution checks for all 6 domains in `scripts/validate.sh`
- [X] T039 [P] [US3] Implement HTTPS health checks for all 6 domains in `scripts/validate.sh`
- [X] T040 [P] [US3] Implement HTTP-to-HTTPS redirect checks for all 6 domains in `scripts/validate.sh`
- [X] T041 [US3] Implement ECR Public intended digest lookup in `scripts/validate.sh`
- [X] T042 [US3] Implement running container digest comparison in `scripts/validate.sh`
- [X] T043 [US3] Add GitHub Actions annotation output for validation failures in `scripts/validate.sh`
- [X] T044 [US3] Wire deploy workflow triggers for `repository_dispatch` and push/merge to infra `main` in `.github/workflows/deploy.yml`
- [X] T045 [US3] Add validation suite documentation cross-reference in `docs/runbook.md`

**Checkpoint**: User Story 3 is independently testable by running the deploy workflow validation.

---

## Phase 6: User Story 4 - Preserve existing domain services (Priority: P4)

**Goal**: Website DNS automation cannot modify mail or other non-site records in Cloudflare.

**Independent Test**: Review Terraform plan and confirm only approved site A-records are created or
updated; any non-site DNS change blocks apply.

### Implementation for User Story 4

- [X] T046 [US4] Restrict Cloudflare Terraform resources to the 6 approved site A-records in `terraform/dns.tf`
- [X] T047 [US4] Add comments warning against mail/non-site DNS ownership in `terraform/dns.tf`
- [X] T048 [US4] Add plan review checklist for DNS safety in `docs/runbook.md`
- [X] T049 [US4] Add workflow failure guidance for non-site DNS plan changes in `.github/workflows/deploy.yml`

**Checkpoint**: User Story 4 is independently testable by inspecting Terraform plan output.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, docs, and safety checks across the whole project.

- [X] T050 [P] Update `README.md` with project purpose, repository roles, and Phase 1 definition of done
- [X] T051 [P] Update `docs/github-secrets.md` with infra-repo and app-repo secret matrix
- [X] T052 [P] Update `docs/runbook.md` with rollback and failed-validation handling
- [X] T053 Run `terraform fmt -recursive` against `terraform/`
- [X] T054 Run `terraform validate` in `terraform/`
- [X] T055 Run `docker compose -f compose/docker-compose.yml config`
- [X] T056 Run quickstart validation steps from `specs/001-infra-static-sites/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on Foundational; can be developed in parallel with US1 after shared Compose names are agreed.
- **US3 (Phase 5)**: Depends on Foundational and benefits from US1/US2 outputs.
- **US4 (Phase 6)**: Depends on Foundational; can be developed in parallel with US1-US3.
- **Polish (Phase 7)**: Depends on selected stories being complete.

### User Story Dependencies

- **US1 (P1)**: MVP. No dependency on other user stories after Foundational.
- **US2 (P2)**: Needs service names and image references from Foundational/US1.
- **US3 (P3)**: Needs deployed service names and validation targets from US1/US2.
- **US4 (P4)**: Independent DNS safety layer after Terraform DNS resources exist.

### Parallel Opportunities

- T002-T005 can run in parallel after T001.
- T006-T012 can be split across Terraform files after directory setup.
- T018-T023 can be prepared in parallel, but final edits converge in `compose/docker-compose.yml`.
- T028-T030 can run in parallel for app-repo templates.
- T037-T040 can run in parallel across workflow and validation script sections.
- T050-T052 can run in parallel during polish.

---

## Parallel Example: User Story 2

```bash
Task: "Create app-repo workflow template in templates/app-repo/.github/workflows/build.yml"
Task: "Create app-repo Dockerfile template in templates/app-repo/Dockerfile"
Task: "Create app-repo static page template in templates/app-repo/index.html"
```

## Parallel Example: User Story 3

```bash
Task: "Implement Terraform validate and plan steps in .github/workflows/deploy.yml"
Task: "Implement DNS resolution checks for all 6 domains in scripts/validate.sh"
Task: "Implement HTTPS health checks for all 6 domains in scripts/validate.sh"
Task: "Implement HTTP-to-HTTPS redirect checks for all 6 domains in scripts/validate.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1.
4. Stop and validate all 6 domains over DNS, HTTPS, and HTTP redirect.

### Incremental Delivery

1. US1: live HTTPS sites on the shared EC2 instance.
2. US2: app-repo build/push/dispatch flow.
3. US3: full deploy validation gates.
4. US4: DNS safety hardening for mail/non-site records.

### Notes

- Do not commit real `.env`, `.ssh/`, keys, cert stores, or Terraform local state.
- Do not add deployment logic to app-repos.
- Do not let Terraform manage mail or non-site DNS records.
- Commit after each task or small logical group.
