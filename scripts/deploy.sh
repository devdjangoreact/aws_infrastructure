#!/usr/bin/env bash
set -euo pipefail

# Pull and (re)start one service from the compose stack on the EC2 host.
# Usage: deploy.sh <service_name> [image_tag]
# Intended to run on the EC2 host (or over SSH) from the compose directory.

SERVICE="${1:-}"
IMAGE_TAG="${2:-latest}"

if [[ -z "${SERVICE}" ]]; then
  echo "::error::service_name is required" >&2
  exit 2
fi

# Approved services (must match compose + data-model).
case "${SERVICE}" in
  buyraq | codehelp | cosmeticpro | ddnsteltonicka | solovkadmytro | solovkaskincare) ;;
  *)
    echo "::error::unknown service '${SERVICE}'" >&2
    exit 2
    ;;
esac

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../compose" && pwd)"
cd "${COMPOSE_DIR}"

# Per-service tag env var, e.g. BUYRAQ_TAG, consumed by docker-compose.yml.
TAG_VAR="$(echo "${SERVICE}" | tr '[:lower:]' '[:upper:]')_TAG"
export "${TAG_VAR}=${IMAGE_TAG}"

docker compose pull "${SERVICE}"
docker compose up -d "${SERVICE}"

echo "Deployed ${SERVICE}:${IMAGE_TAG}"
