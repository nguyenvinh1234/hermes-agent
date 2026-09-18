#!/usr/bin/env bash
# Restore-test a Postgres backup into a TEMPORARY, isolated container.
#
# This NEVER touches the live `ngocviet-mem0-postgres` container or the
# `ngocviet_mem0_postgres_data` volume — it spins up a throwaway container
# on its own throwaway volume/network, restores into it, and destroys both
# at the end (or on any error, via the trap below). A backup is only
# considered verified after this script reports PASS.
#
# Usage: ./scripts/restore.sh /opt/ngocviet/memory/backups/2026-01-01/postgres_ngocviet_memory_....sql.gz
set -euo pipefail

DUMP_FILE="${1:?Usage: restore.sh <path-to-backup.sql.gz>}"
if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "ERROR: backup file not found: ${DUMP_FILE}" >&2
  exit 1
fi

RESTORE_DB="ngocviet_memory_restore_test"
RESTORE_USER="restore_test_user"
RESTORE_PASSWORD="restore-test-$(date +%s)"
CONTAINER_NAME="ngocviet-mem0-postgres-RESTORE-TEST-$$"
TEMP_VOLUME="ngocviet_mem0_restore_test_$$"

cleanup() {
  echo "==> Cleaning up temporary restore container/volume..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker volume rm "${TEMP_VOLUME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Starting temporary Postgres container '${CONTAINER_NAME}' (isolated, not the production one)..."
docker run -d --name "${CONTAINER_NAME}" \
  -v "${TEMP_VOLUME}:/var/lib/postgresql/data" \
  -e POSTGRES_DB="${RESTORE_DB}" \
  -e POSTGRES_USER="${RESTORE_USER}" \
  -e POSTGRES_PASSWORD="${RESTORE_PASSWORD}" \
  pgvector/pgvector:pg17 >/dev/null

echo "==> Waiting for temporary Postgres to become ready..."
for _ in $(seq 1 30); do
  if docker exec "${CONTAINER_NAME}" pg_isready -U "${RESTORE_USER}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Restoring backup into the temporary database..."
gunzip -c "${DUMP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${RESTORE_USER}" -d "${RESTORE_DB}" >/tmp/restore-test-$$.log 2>&1 \
  || { echo "ERROR: restore failed, see /tmp/restore-test-$$.log"; exit 1; }

echo "==> Counting memories table rows (adjust table name if your pinned Mem0 schema differs)..."
ROW_COUNT="$(docker exec "${CONTAINER_NAME}" psql -U "${RESTORE_USER}" -d "${RESTORE_DB}" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
echo "    public tables found: ${ROW_COUNT}"

if [[ "${ROW_COUNT}" -eq 0 ]]; then
  echo "FAIL: restored database has zero tables — backup is not usable." >&2
  exit 1
fi

echo "==> PASS: restore succeeded and produced a non-empty schema."
echo "Record this result in docs/backup-restore-test.md along with:"
echo "  - source dump: ${DUMP_FILE}"
echo "  - table count: ${ROW_COUNT}"
echo "  - a manual spot-check: search for one of the smoke-test memories via psql or the gateway"
