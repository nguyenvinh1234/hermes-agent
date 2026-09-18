#!/usr/bin/env bash
# Quick health/readiness probe for the gateway. Exits non-zero on failure so
# it can be used in cron/monitoring.
#
# Usage: GATEWAY_URL=http://127.0.0.1:8077 ./scripts/healthcheck.sh
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8077}"

echo "==> GET ${GATEWAY_URL}/health"
health_status="$(curl -sS -o /tmp/health-body-$$.json -w '%{http_code}' "${GATEWAY_URL}/health" || echo "000")"
cat /tmp/health-body-$$.json 2>/dev/null || true
echo
rm -f /tmp/health-body-$$.json

if [[ "${health_status}" != "200" ]]; then
  echo "FAIL: /health returned ${health_status}" >&2
  exit 1
fi

echo "==> GET ${GATEWAY_URL}/ready"
ready_body_file="/tmp/ready-body-$$.json"
ready_status="$(curl -sS -o "${ready_body_file}" -w '%{http_code}' "${GATEWAY_URL}/ready" || echo "000")"
cat "${ready_body_file}" 2>/dev/null || true
echo
rm -f "${ready_body_file}"

if [[ "${ready_status}" != "200" ]]; then
  echo "FAIL: /ready returned ${ready_status} (gateway up, but Mem0/Postgres chain is not ready)" >&2
  exit 1
fi

echo "PASS: gateway healthy and ready."
