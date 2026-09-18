# NgocViet Memory

A self-hosted shared agent-memory subsystem: **Mem0 + PostgreSQL/pgvector**
behind the **NgocViet Memory Gateway**, the single access path for Hermes,
OpenClaw, and future callers (n8n, DeepSeek Harness, Codex, ...).

```
Hermes ─────┐
            │
OpenClaw ───┼──► NgocViet Memory Gateway ─► Mem0 (self-hosted) ─► PostgreSQL + pgvector
            │
n8n /       │
DeepSeek /  │
Codex ──────┘
```

**This is an independent subsystem, not a Hermes core feature.** It lives
entirely under this one directory, has no import dependency on the rest of
`hermes-agent`, ships its own Docker Compose stack that runs standalone,
and integrates with Hermes only through a standalone plugin — never a core
file edit. See "Designed to be extracted" below.

## Status

Code, tests, docs, and scripts only. **Nothing has been deployed** — this
was built in a sandboxed session with no SSH/Docker access to any real
server (see `docs/server-audit-checklist.md`). Every "PASS" in this
subproject's tests refers to sandbox unit tests against a mocked Mem0, not
a live production stack. Follow `docs/deployment.md` on the real target
server before trusting any of this in production.

## Layout

```
integrations/ngocviet-memory/
├── gateway/            # FastAPI app — the only thing that talks to Mem0
│   ├── app/
│   ├── tests/          # 26 passing unit/integration tests (mocked Mem0)
│   ├── Dockerfile
│   └── requirements.txt
├── hermes-adapter/      # Standalone Hermes plugin (memory_search/add/feedback)
├── docker/
│   └── docker-compose.yml   # Postgres + Mem0 + Gateway, isolated network
├── scripts/
│   ├── backup.sh restore.sh healthcheck.sh smoke-test.sh server-audit.sh
├── docs/
│   ├── architecture.md security.md api-contract.md
│   ├── deployment.md backup-restore.md
│   ├── hermes-integration.md openclaw-integration-plan.md
│   ├── hermes-test-cases.md server-audit-checklist.md
│   └── backup-restore-test.md
├── .env.example
└── CHANGELOG.md
```

## Quick start (real server only)

```bash
cd integrations/ngocviet-memory
cp .env.example .env   # fill in real secrets — see docs/security.md
# Phase 0: read docs/deployment.md and run scripts/server-audit.sh on the
# real target server FIRST. Do not skip to the steps below until it says READY.
cd docker
docker compose --env-file ../.env config   # dry run
docker compose --env-file ../.env up -d
```

Full phase-by-phase runbook (mandatory order: audit → Mem0 → gateway →
backup/restore → Hermes adapter → Hermes tests → OpenClaw assessment):
`docs/deployment.md`.

## Designed to be extracted into its own repo

Nothing under this directory imports from anywhere else in `hermes-agent`:

- `gateway/` only imports `fastapi`/`pydantic`/`httpx` — zero Hermes
  imports.
- `docker/docker-compose.yml` only references paths inside this directory.
- `hermes-adapter/` talks to Hermes only through the plugin `register(ctx)`
  contract (an external interface, not an internal import) and to the
  gateway only over HTTP.
- `scripts/` and `docs/` use paths relative to this directory.

To split it out as `nguyenvinh1234/ngocviet-memory` later:
```bash
git subtree split --prefix=integrations/ngocviet-memory -b ngocviet-memory-extract
# push that branch to a new repo, or:
# cp -r integrations/ngocviet-memory /path/to/new/repo && cd /path/to/new/repo && git init
```
No import paths, no `sys.path` hacks, and no Hermes-internal module
references need fixing up afterward.

## Why a gateway instead of direct access

See `docs/architecture.md`. Short version: least privilege (only the
gateway ever holds the Mem0 admin key), consistent policy enforcement
across every future client, and a single place for auth/rate-limit/
sensitive-data-filter/audit-log — all without touching Hermes, OpenClaw, or
whatever calls this next.

## Key documents

| Doc | What it's for |
|---|---|
| `docs/architecture.md` | Namespace model, memory classes, data flow |
| `docs/deployment.md` | Phase-by-phase rollout runbook |
| `docs/security.md` | Threat model, what each client never gets |
| `docs/api-contract.md` | The stable multi-client HTTP contract |
| `docs/backup-restore.md` | Backup/restore/retention procedure |
| `docs/hermes-integration.md` | Adapter design, recall/write flow, rollback |
| `docs/openclaw-integration-plan.md` | Assessment only — no prod changes |
| `docs/hermes-test-cases.md` | 35 test cases to run in Phase 6 |
| `docs/server-audit-checklist.md` + `scripts/server-audit.sh` | Phase 0, real server only |

## Safety rules this subproject follows

No `docker system prune`/`volume prune` anywhere in these scripts, no
container/volume deletion outside ones this subsystem itself created (and
those only in `restore.sh`'s throwaway test container), no Postgres/Mem0
port published to `0.0.0.0` or the internet, no secret ever hardcoded or
logged, `.env` gitignored with `.env.example` the only tracked template.
Full list: `docs/security.md`.
