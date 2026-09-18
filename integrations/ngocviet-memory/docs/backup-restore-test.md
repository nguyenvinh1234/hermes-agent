# Backup/Restore Test Log

No restore test has been run yet — this file has no entries because
nothing has actually been deployed from this build session (see
`docs/server-audit-checklist.md` for why). Append one entry per test, in the
format below, every time `scripts/restore.sh` is run for real.

## Entry template

```
### YYYY-MM-DD HH:MM UTC

- Source dump: /opt/ngocviet/memory/backups/YYYY-MM-DD/postgres_..._....sql.gz
- Dump size: <bytes>
- Restore duration: <seconds>
- Public tables found in restored schema: <count>
- Manual spot-check: <what you queried, and what came back>
- Result: PASS | FAIL
- Notes: <anything unusual>
```
