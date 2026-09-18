# Security

## Secrets

- All real secrets live in `.env` (gitignored) — see `.env.example` for the
  full placeholder list. Never commit `.env`, never paste its contents into
  chat/tickets/logs.
- The Mem0 admin/master key (`MEM0_API_KEY`) exists **only** in the
  gateway container's environment. Hermes and OpenClaw never see it —
  they only ever hold their own `MEMORY_GATEWAY_API_KEY_*` value.
- Run a secret scanner (e.g. `gitleaks detect` or `trufflehog filesystem
  .`) before every commit to this subproject. Neither ships with the repo
  here — install whichever your org already uses.

## Network exposure

- `postgres` and `mem0` containers publish **no host ports** at all —
  reachable only from other containers on the `ngocviet-memory-net` Docker
  network. There is no `0.0.0.0` bind anywhere for either of them.
- `gateway` binds to `127.0.0.1` by default (`GATEWAY_BIND_HOST` in
  `.env.example`). If Hermes/OpenClaw run outside this Docker network and
  need to reach it over the network, put a reverse proxy (Nginx/Traefik/
  Caddy — whichever the server already runs) in front with its own TLS and
  IP allowlisting, rather than binding the gateway to `0.0.0.0` directly.
- Never expose Mem0's admin API or Postgres to the internet, directly or
  through a proxy. Only the gateway's `/v1/memory/*` and `/health`/`/ready`
  should ever be reachable from outside the Docker network, and only to
  Hermes/OpenClaw's own network location.

## AuthN/AuthZ

- Each client (Hermes, OpenClaw) gets its own `X-NgocViet-API-Key`. Keys
  are never shared between clients and never rotated by copy-paste between
  `.env` entries — generate independently (e.g. `openssl rand -hex 32`).
- A client cannot set its own `agent_id`/`app_id` — enforced at the schema
  layer (`extra="forbid"`), not just by convention.
- A client cannot update or delete another agent's `agent_private`/
  `project`/`temporary` memory (403), even if it somehow learns the
  memory's id.

## Sensitive-data filter

`gateway/app/sensitive_data.py` rejects (not redacts-and-stores) content
matching private-key blocks, `sk-...`/`ghp_...`/`github_pat_...` tokens,
`Bearer ...` headers, AWS access key IDs, generic
`password=`/`api_key=`-style assignments, and `user:pass@host` URLs. This
is a best-effort regex filter, not a guarantee — it catches the patterns
named explicitly in the rollout spec, not every possible secret shape.
Treat it as defense in depth, not a substitute for not writing secrets into
memory content in the first place.

On a match, the audit log records `"reason": "REDACTED_SECRET"` and the
pattern name only — never the matched text or surrounding content.

## Rate limiting

In-memory, per-client, fixed 60s window (`gateway/app/ratelimit.py`).
**Known limitation:** this only works correctly with a single gateway
replica. If you ever scale the gateway horizontally, replace this with a
shared store (Redis) before relying on it.

## Audit logging

Every `/v1/memory/*` operation logs a structured JSON line (section 14 of
the rollout spec) to stdout: `timestamp, client_id, operation, user_id,
project_id, status, latency_ms`, plus `error`/`reason` on failure. Never
logs API keys, passwords, or full memory content. Rotation is handled by
Docker's `json-file` log driver (`max-size: 10m`, `max-file: 5` — see
`docker/docker-compose.yml`), not by the application.

## Timeouts, retries, and failure isolation

- Every Mem0 call has an 8s timeout (`MEM0_REQUEST_TIMEOUT_SECONDS`) and at
  most one retry, only for transport-level errors (connection refused,
  timeout) — never for 4xx responses, and never for DELETE.
- If Mem0/Postgres is down, `/v1/memory/*` returns `502`/`504` rather than
  hanging. `/ready` reports `false`. The gateway process itself stays up.
- Hermes' own graceful-degradation behavior when the gateway is
  unreachable is documented in `docs/hermes-integration.md` "Rollback /
  failure modes" — Hermes must never hard-fail a conversation because
  memory is down.

## What Hermes/OpenClaw are never given

- Direct PostgreSQL access (credentials, port, or otherwise).
- The Mem0 admin/master key.
- A `delete` capability via the Hermes adapter (the HTTP DELETE route
  exists at the gateway for administrative use, but the Hermes plugin
  never calls it — see `docs/hermes-integration.md`).
- The ability to set their own `agent_id`/`app_id` on a write.

## Threats explicitly out of scope for v1

- Multi-tenant isolation beyond `agent_id`/`project_id` (e.g. per-end-user
  row-level encryption) — not required by the current spec.
- Protecting against a fully compromised gateway host (if the host is
  compromised, the attacker has the Mem0 admin key regardless of any
  application-layer control here). Host hardening is a server-level
  concern, not this gateway's.
