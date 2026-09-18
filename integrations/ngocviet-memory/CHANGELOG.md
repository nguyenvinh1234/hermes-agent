# Changelog

All notable changes to the NgocViet Memory subsystem.

## [Unreleased]

### Added

- Initial NgocViet Memory Gateway (FastAPI): `/health`, `/ready`,
  `POST /v1/memory/add`, `POST /v1/memory/search`, `GET|PATCH|DELETE
  /v1/memory/{id}`.
- Namespace/policy engine: `agent_id`/`app_id` server-injected only,
  `memory_class` (`shared`/`agent_private`/`project`/`temporary`) visibility
  enforcement, status (`active`/`superseded`/`archived`) filtering, TTL for
  temporary memories.
- Sensitive-data filter (reject-on-detect) for private keys, API tokens,
  bearer headers, password assignments, basic-auth URLs.
- Per-client API key auth, generic client registry
  (`MEMORY_GATEWAY_CLIENT_IDS`) so future callers (n8n, DeepSeek Harness,
  Codex) can be onboarded via `.env` only.
- Per-client rate limiting (in-memory, single-instance).
- Structured JSON audit logging.
- 26 gateway unit/integration tests (mocked Mem0), all passing.
- Docker Compose stack: Postgres/pgvector (no published port) + Mem0
  (vendored/pinned build, no published port) + Gateway (127.0.0.1 by
  default) on an isolated `ngocviet-memory-net` network.
- `scripts/`: `backup.sh`, `restore.sh` (isolated temp-container restore
  test), `healthcheck.sh`, `smoke-test.sh`, `server-audit.sh` (read-only,
  for the real server).
- Standalone Hermes plugin (`hermes-adapter/`): `memory_search`,
  `memory_add`, `memory_feedback` tools, no delete capability, graceful
  degradation on gateway failure, 6 passing tests.
- Full docs set: architecture, deployment runbook, security, API contract,
  backup/restore, Hermes integration, OpenClaw integration plan (assessment
  only), 35-case Hermes test plan, server audit checklist.

### Not done yet (by design — see docs/deployment.md)

- Nothing has been deployed to any real server.
- Mem0 source is not vendored/pinned yet — the exact commit SHA must be
  chosen and verified by whoever runs Phase 1, not assumed from this
  changelog.
- No live backup/restore test has been run (`docs/backup-restore-test.md`
  is empty by design).
- No live Hermes test report exists yet (`docs/hermes-test-cases.md` is a
  plan, not a report).
- OpenClaw integration: assessment doc only, several sections marked
  `<TO FILL IN>` pending real access to OpenClaw's deployment.
