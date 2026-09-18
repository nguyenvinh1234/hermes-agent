#!/usr/bin/env bash
# End-to-end smoke test against a LIVE gateway (section 19).
# ADD -> GET -> SEARCH -> UPDATE -> SEARCH updated -> DELETE -> confirm missing.
#
# Requires: curl, jq
# Usage:
#   GATEWAY_URL=http://127.0.0.1:8077 \
#   API_KEY=$MEMORY_GATEWAY_API_KEY_HERMES \
#   ./scripts/smoke-test.sh
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8077}"
API_KEY="${API_KEY:?Set API_KEY to a valid MEMORY_GATEWAY_API_KEY_* value}"
USER_ID="${USER_ID:-ngocviet-owner}"

fail=0
pass_count=0
total_count=0

check() {
  local desc="$1" expected="$2" actual="$3"
  total_count=$((total_count + 1))
  if [[ "${actual}" == "${expected}" ]]; then
    echo "  PASS: ${desc}"
    pass_count=$((pass_count + 1))
  else
    echo "  FAIL: ${desc} (expected ${expected}, got ${actual})"
    fail=1
  fi
}

req() {
  local method="$1" path="$2" body="${3:-}"
  if [[ -n "${body}" ]]; then
    curl -sS -X "${method}" "${GATEWAY_URL}${path}" \
      -H "X-NgocViet-API-Key: ${API_KEY}" -H "Content-Type: application/json" \
      -d "${body}" -w '\n%{http_code}'
  else
    curl -sS -X "${method}" "${GATEWAY_URL}${path}" \
      -H "X-NgocViet-API-Key: ${API_KEY}" -w '\n%{http_code}'
  fi
}

echo "=== 1. ADD ==="
add_out="$(req POST /v1/memory/add '{"user_id":"'"${USER_ID}"'","content":"The company uses Hermes as orchestration hub.","memory_class":"shared","project_id":"global","domain":"architecture"}')"
add_code="$(tail -n1 <<<"${add_out}")"
add_body="$(sed '$d' <<<"${add_out}")"
check "ADD returns 201" "201" "${add_code}"
memory_id="$(jq -r '.id // empty' <<<"${add_body}")"
if [[ -z "${memory_id}" ]]; then
  echo "  FAIL: no memory id returned, cannot continue smoke test." >&2
  exit 1
fi
echo "  memory_id=${memory_id}"

echo "=== 2. GET ==="
get_out="$(req GET "/v1/memory/${memory_id}")"
get_code="$(tail -n1 <<<"${get_out}")"
check "GET returns 200" "200" "${get_code}"

echo "=== 3. SEARCH ==="
search_out="$(req POST /v1/memory/search '{"user_id":"'"${USER_ID}"'","query":"Hermes orchestration hub","memory_class":["shared"],"project_id":"global","limit":8}')"
search_code="$(tail -n1 <<<"${search_out}")"
search_body="$(sed '$d' <<<"${search_out}")"
check "SEARCH returns 200" "200" "${search_code}"
found="$(jq -r --arg id "${memory_id}" '[.results[] | select(.id == $id)] | length' <<<"${search_body}")"
check "SEARCH finds the new memory" "1" "${found}"

echo "=== 4. UPDATE ==="
update_out="$(req PATCH "/v1/memory/${memory_id}" '{"content":"Hermes acts as the main orchestrator.","status":"active"}')"
update_code="$(tail -n1 <<<"${update_out}")"
check "UPDATE returns 200" "200" "${update_code}"

echo "=== 5. SEARCH updated ==="
search2_out="$(req POST /v1/memory/search '{"user_id":"'"${USER_ID}"'","query":"main orchestrator","memory_class":["shared"],"project_id":"global","limit":8}')"
search2_code="$(tail -n1 <<<"${search2_out}")"
check "SEARCH after update returns 200" "200" "${search2_code}"

echo "=== 6. DELETE ==="
delete_out="$(req DELETE "/v1/memory/${memory_id}")"
delete_code="$(tail -n1 <<<"${delete_out}")"
check "DELETE returns 200" "200" "${delete_code}"

echo "=== 7. Confirm missing ==="
confirm_out="$(req GET "/v1/memory/${memory_id}")"
confirm_code="$(tail -n1 <<<"${confirm_out}")"
check "GET after DELETE returns 404" "404" "${confirm_code}"

echo
echo "=== Summary: ${pass_count}/${total_count} checks passed ==="
if [[ "${fail}" -ne 0 ]]; then
  echo "SMOKE TEST: FAIL"
  exit 1
fi
echo "SMOKE TEST: PASS"
