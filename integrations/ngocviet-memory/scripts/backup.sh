#!/usr/bin/env bash
# Backup the NgocViet Memory Postgres database + stack config.
#
# Safety: read-only against the live stack (pg_dump only, never touches
# volumes/containers), writes only under BACKUP_ROOT, never overwrites an
# existing backup (timestamped filenames), and only ever deletes files it
# itself created earlier, matched by name pattern, during retention pruning.
#
# Usage: ./scripts/backup.sh
# Env (optional overrides): BACKUP_ROOT, RETENTION_DAYS, ENV_FILE, COMPOSE_FILE
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_ROOT}/docker/docker-compose.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/ngocviet/memory/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found. Copy .env.example to .env first." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

: "${POSTGRES_DB:?POSTGRES_DB must be set in .env}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in .env}"

DATE_DIR="$(date -u +%Y-%m-%d)"
STAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"
TARGET_DIR="${BACKUP_ROOT}/${DATE_DIR}"
mkdir -p "${TARGET_DIR}"

DUMP_FILE="${TARGET_DIR}/postgres_${POSTGRES_DB}_${STAMP}.sql.gz"
if [[ -e "${DUMP_FILE}" ]]; then
  echo "ERROR: ${DUMP_FILE} already exists, refusing to overwrite." >&2
  exit 1
fi

echo "==> Dumping database '${POSTGRES_DB}' from the postgres container..."
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --format=plain \
  | gzip > "${DUMP_FILE}"

if [[ ! -s "${DUMP_FILE}" ]]; then
  echo "ERROR: dump file is empty — treating backup as FAILED." >&2
  rm -f "${DUMP_FILE}"
  exit 1
fi

echo "==> Copying stack config (compose file, gateway app source) — NOT .env (secrets)."
CONFIG_SNAPSHOT="${TARGET_DIR}/config_${STAMP}.tar.gz"
tar -czf "${CONFIG_SNAPSHOT}" \
  -C "${PROJECT_ROOT}" \
  docker/docker-compose.yml gateway/app gateway/requirements.txt gateway/Dockerfile .env.example

echo "==> Backup complete:"
echo "    ${DUMP_FILE}"
echo "    ${CONFIG_SNAPSHOT}"
echo "NOTE: .env was intentionally excluded. If you need it backed up, encrypt"
echo "it yourself first (e.g. 'gpg -c .env') and store the .gpg file separately."

echo "==> Applying retention policy (${RETENTION_DAYS} days) under ${BACKUP_ROOT}..."
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime "+${RETENTION_DAYS}" -print | while read -r old_dir; do
  echo "    pruning old backup dir: ${old_dir}"
  rm -rf -- "${old_dir}"
done

echo "==> Done. Remember: a backup is not verified until restore.sh has been run against it."
