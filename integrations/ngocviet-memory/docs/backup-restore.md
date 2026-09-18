# Backup & Restore

## Backup

`scripts/backup.sh`:

1. `pg_dump`s the `ngocviet_memory` database from the live `postgres`
   container (read-only against the running stack — no container is
   stopped or modified).
2. Writes a gzipped dump to
   `/opt/ngocviet/memory/backups/YYYY-MM-DD/postgres_<db>_<timestamp>.sql.gz`
   (override the root via `BACKUP_ROOT`). Never overwrites an existing file
   — timestamped down to the second.
3. Also archives the compose file + gateway app source (not `.env` —
   secrets are excluded by default; encrypt it yourself with `gpg -c .env`
   if you want it included).
4. Prunes dated backup directories older than `RETENTION_DAYS` (default 14)
   under `BACKUP_ROOT` only — never touches anything outside that root.

Run it manually or via cron, e.g.:
```
0 3 * * * /opt/ngocviet/memory/ngocviet-memory/scripts/backup.sh >> /opt/ngocviet/memory/logs/backup.log 2>&1
```

**A `pg_dump` exit code of 0 is not proof the backup is usable** — per the
rollout spec, no backup is considered successful until `restore.sh` has
been run against it.

## Restore test

`scripts/restore.sh <path-to-dump.sql.gz>`:

1. Starts a **temporary**, throwaway Postgres container (its own container
   name and volume, both suffixed with the script's PID) — the live
   `ngocviet-mem0-postgres` container and its volume are never touched.
2. Restores the dump into it.
3. Counts tables in the restored schema as a sanity check.
4. Destroys the temporary container and volume on exit (including on
   failure, via a trap).

Record every restore test's outcome in a dated entry appended to
`docs/backup-restore-test.md` (template below) — id, source dump path,
table count, and a manual spot-check (e.g. querying one of the smoke-test
memories back out via `psql` against the temp container, or — if you want
to test the full path — pointing a throwaway gateway/Mem0 pair at the
restored data and running `scripts/smoke-test.sh`'s SEARCH step against
it).

## Restore into production (disaster recovery — manual, deliberate)

This repo does not provide a one-command "restore into prod" script on
purpose — restoring over live data is destructive and must be a deliberate,
reviewed action, not something a script can be accidentally re-run. Runbook:

1. Stop the `gateway` service (not `postgres`/`mem0`) so nothing is writing
   during the restore: `docker compose stop gateway`.
2. Take a fresh backup of the *current* (about-to-be-overwritten) database
   first, in case the restore itself needs to be rolled back.
3. `docker compose exec -T postgres psql -U $POSTGRES_USER -d $POSTGRES_DB`
   and restore the chosen dump (`\i` or pipe via `psql` as in
   `restore.sh`, but against the real container this time — done by a
   human, not a script, with the two backups from steps 1–2 open in
   another terminal).
4. `docker compose start gateway`, then run `scripts/healthcheck.sh` and
   `scripts/smoke-test.sh`.
5. Document what happened and why in `CHANGELOG.md`.

## Retention

Default 14 days of dated backup directories under `BACKUP_ROOT`. Adjust
`RETENTION_DAYS` based on actual disk headroom found during the Phase 0
audit (`docs/server-audit-checklist.md`) — don't raise it blindly on a disk
that's already tight.
