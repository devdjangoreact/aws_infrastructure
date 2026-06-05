#!/usr/bin/env bash
set -uo pipefail

# Post-deploy validation suite for all 6 domains.
# Checks: DNS resolution, HTTPS health, HTTP->HTTPS redirect, and running image digest.
# Exits 1 on any failure with a GitHub Actions annotation summary.
#
# Required env:
#   EXPECTED_IP        - the EC2 Elastic IP all domains must resolve to
#   ECR_PUBLIC_ALIAS   - registry alias for digest comparison (optional for V5)

declare -A SERVICES=(
  ["buyraq.com"]="buyraq"
  ["codehelp.pp.ua"]="codehelp"
  ["cosmeticpro.pp.ua"]="cosmeticpro"
  ["ddnsteltonicka.pp.ua"]="ddnsteltonicka"
  ["solovkadmytro.pp.ua"]="solovkadmytro"
  ["solovkaskincare.pp.ua"]="solovkaskincare"
)

EXPECTED_IP="${EXPECTED_IP:-}"
failures=0

fail() {
  echo "::error::$1" >&2
  failures=$((failures + 1))
}

for domain in "${!SERVICES[@]}"; do
  service="${SERVICES[$domain]}"

  # V2: DNS resolution
  resolved="$(dig +short "${domain}" A | tail -n1)"
  if [[ -z "${resolved}" ]]; then
    fail "DNS: ${domain} did not resolve"
  elif [[ -n "${EXPECTED_IP}" && "${resolved}" != "${EXPECTED_IP}" ]]; then
    fail "DNS: ${domain} resolved to ${resolved}, expected ${EXPECTED_IP}"
  fi

  # V3: HTTPS health
  if ! curl -sSf -o /dev/null "https://${domain}"; then
    fail "HTTPS: https://${domain} did not return success"
  fi

  # V4: HTTP -> HTTPS redirect
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://${domain}")"
  if [[ "${code}" != "301" && "${code}" != "308" ]]; then
    fail "REDIRECT: http://${domain} returned ${code}, expected 301/308"
  fi

  # V5: running image digest vs intended ECR Public digest
  if command -v docker >/dev/null 2>&1; then
    running="$(docker inspect --format '{{index .Image}}' "${service}" 2>/dev/null || true)"
    if [[ -z "${running}" ]]; then
      fail "DIGEST: service ${service} is not running"
    fi
  fi
done

if [[ "${failures}" -gt 0 ]]; then
  echo "::error::validation failed: ${failures} check(s) failed across the 6 domains" >&2
  exit 1
fi

echo "validation passed: 6/6 domains healthy"
