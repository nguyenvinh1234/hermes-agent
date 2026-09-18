# Deployment Runbook

Follow phases in order. Do not skip ahead — each phase's exit criteria
gates the next one. Every command below is meant to be run **on the target
server**, by a human (or a session with real SSH/Docker access to it) —
none of it was run as part of producing this repo; see the top-level
README for why.

Safety reminders that apply to every phase (full list in
`docs/security.md` and the original rollout spec): never `docker system
prune` / `docker volume prune`, never touch an Odoo/n8n/OpenClaw
production container or its data, never publish Postgres or Mem0's admin
API to `0.0.0.0`, never commit `.env`.

## Phase 0 — Server audit (read-only)

1. On the real target server, run `../scripts/server-audit.sh` (from
   `docs/`) — it's read-only, changes nothing, and writes one timestamped
   raw report under `audit-reports/`.
2. Fill in `docs/server-audit-checklist.md` directly using that report:
   every section, including the port table and the "Manual follow-ups"
   items the script can't judge for you (is a hit actually Odoo's? is disk
   already tight? does `ngocviet-memory-net` already exist?).
3. Conclude `READY` or `BLOCKED` in that same file. If `BLOCKED`, stop and
   resolve the conflict before continuing — do not deploy anything.

## Phase 1 — Mem0 (isolated, no Hermes/OpenClaw yet)

1. Pick a commit SHA on https://github.com/mem0ai/mem0 yourself and verify
   it (browse the repo at that SHA, confirm `server/` exists and looks
   sane). **Do not trust a tag/version name suggested by any AI tool,
   including this one** — a web lookup performed while building this repo
   returned an implausible tag list (unrelated project names, all dated the
   same day) that looked unreliable, so no version was pinned here for
   you. Pick your own and put the full 40-char SHA in
   `MEM0_SOURCE_GIT_REF`.
2. Vendor it:
   ```bash
   mkdir -p /opt/ngocviet/memory/vendor
   git clone https://github.com/mem0ai/mem0.git /opt/ngocviet/memory/vendor/mem0
   cd /opt/ngocviet/memory/vendor/mem0
   git checkout <the-commit-sha-you-verified>
   ```
3. Open `vendor/mem0/server/main.py` and `server/auth.py` (or wherever auth
   lives at your pinned commit) and confirm the auth header format and the
   env vars it expects. Update `MEM0_AUTH_HEADER`/`MEM0_AUTH_SCHEME` in
   `.env` and the `mem0:` service's `environment:` block in
   `docker/docker-compose.yml` if they differ from what's there.
4. Create `/opt/ngocviet/memory/{mem0,gateway,backups,logs,scripts,docs}`
   and copy this subproject there (or work directly from a checkout of
   this git branch — either is fine, `docker-compose.yml` uses relative
   paths).
5. Copy `.env.example` to `.env`, fill in `POSTGRES_*`, `MEM0_API_KEY`,
   `MEM0_JWT_SECRET`, `LLM_PROVIDER`/`LLM_API_KEY`, and
   `MEM0_SOURCE_DIR=/opt/ngocviet/memory/vendor/mem0`. Leave
   `MEMORY_GATEWAY_API_KEY_*` blank for now — not needed until Phase 2.
6. Bring up only Postgres and Mem0:
   ```bash
   cd docker
   docker compose --env-file ../.env config   # dry-run, read the rendered config first
   docker compose --env-file ../.env up -d postgres mem0
   docker compose --env-file ../.env ps
   docker compose --env-file ../.env logs -f mem0   # watch for startup errors
   ```

## Phase 2 — Kiểm tra Mem0

Confirm Mem0 is actually working before building on top of it:

```bash
docker compose --env-file ../.env exec mem0 python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/').status)"
```

Then, from inside the `ngocviet-memory-net` network (e.g.
`docker run --rm --network ngocviet-memory-net curlimages/curl ...`), issue
a raw `POST /memories` and `POST /search` against Mem0 directly using
`MEM0_API_KEY`, per whatever auth header you confirmed in Phase 1. Record
what you saw. Do not proceed to Phase 3 until this round-trips.

## Phase 3 — Gateway

1. Generate two independent keys:
   ```bash
   openssl rand -hex 32   # -> MEMORY_GATEWAY_API_KEY_HERMES
   openssl rand -hex 32   # -> MEMORY_GATEWAY_API_KEY_OPENCLAW
   ```
2. Fill them into `.env`, confirm `GATEWAY_BIND_PORT` is free (from your
   Phase 0 audit table).
3. `docker compose --env-file ../.env up -d --build gateway`
4. `../scripts/healthcheck.sh` (set `GATEWAY_URL` if you changed the port).
5. `API_KEY=<hermes key> ../scripts/smoke-test.sh` — must report `PASS`
   (7/7 checks). This exercises ADD/GET/SEARCH/UPDATE/SEARCH/DELETE/confirm
   missing end to end, satisfying section 19 of the rollout spec.
6. Manually verify namespace security (section 20): add an
   `agent_private` memory with the Hermes key, confirm the OpenClaw key
   cannot see it in search; add a `shared` one and confirm OpenClaw *can*
   see it; add a `project` one under `project_id=obsidian` and confirm it
   does not appear when searching `project_id=mach3-turret`.

## Phase 4 — Backup / Restore

1. `../scripts/backup.sh`
2. `../scripts/restore.sh <the dump it just produced>` — must report `PASS`.
3. Append the result to `docs/backup-restore-test.md`.

Do not proceed to Phase 5 until this is PASS — an unverified backup is not
a backup.

## Phase 5 — Hermes adapter

Only after Phases 1–4 all PASS.

1. Read `integrations/ngocviet-memory/hermes-adapter/README.md` — it's a
   standalone plugin, installed under `~/.hermes/plugins/memory_gateway/`
   or via pip entry point, **not** merged into this repo's own
   `plugins/` tree (repo policy — see `plugins/AGENTS.md`).
2. Set `MEMORY_GATEWAY_URL` and `MEMORY_GATEWAY_API_KEY` in the environment
   Hermes actually runs in (its own `.env`/`~/.hermes/`, not this
   subproject's).
3. Initial config: `read enabled, write filtered, delete disabled` (the
   adapter has no delete tool at all — see `docs/hermes-integration.md`).
4. Validate the plugin loads: `hermes plugins doctor
   ~/.hermes/plugins/memory_gateway --ci` (or wherever you installed it).

## Phase 6 — Hermes test

Run the test cases in `docs/hermes-test-cases.md` against a real Hermes
session with the adapter enabled. Record actual results (not assumed ones)
in a new `docs/hermes-test-report.md`, concluding `PASS` /
`PASS WITH WARNINGS` / `FAIL` per section 19/37 of the rollout spec.

Also exercise the failure modes explicitly (section 33): stop the
`gateway` container mid-conversation and confirm Hermes keeps working
(logs a warning, skips memory, does not hard-fail) before calling this
phase done.

## Phase 7 — OpenClaw (assessment only)

Do not touch OpenClaw production. Only produce
`docs/openclaw-integration-plan.md` (already drafted here — review and
update it against OpenClaw's actual current state, which this build
session had no access to).

## Definition of Done

Copy the checklist from the rollout spec (section 37) into your PR/ticket
and check items off only against real evidence (a log line, a script's
PASS output, a file diff) — not from memory.

## Rollback

- **Gateway**: `docker compose --env-file ../.env stop gateway` — Mem0/
  Postgres are untouched, Hermes should degrade gracefully (see
  `docs/hermes-integration.md`).
- **Mem0**: `docker compose --env-file ../.env stop mem0` — gateway starts
  returning 502/504, same graceful-degradation path.
- **Full stack**: `docker compose --env-file ../.env down` (no `-v` — this
  keeps `ngocviet_mem0_postgres_data`). Add `-v` only if you have a
  verified-restorable backup and intend to discard the data.
- **Hermes adapter**: remove/disable the plugin directory (or unset
  `MEMORY_GATEWAY_API_KEY` in Hermes' own env) — Hermes falls back to its
  prior behavior with no memory recall/write. No core Hermes file was ever
  modified, so there's nothing to revert there.
