# Architecture

## Goal

A single shared agent-memory service that Hermes and (later) OpenClaw both
read/write through, with namespace isolation, auditability, backup/restore
and rollback — without either agent ever touching Postgres directly or
holding Mem0's admin key.

```
Hermes ─────┐
            │
OpenClaw ───┼──► NgocViet Memory Gateway ─► Mem0 (self-hosted) ─► PostgreSQL + pgvector
            │
Future ─────┘
```

- **Odoo** stays the operational source of truth. Untouched.
- **Obsidian** stays the knowledge source of truth. Untouched.
- **Mem0** stores only what's needed for agent memory — not an import
  target for Odoo or Obsidian data.
- **NgocViet Memory Gateway** is the only thing that talks to Mem0. It is
  the only component that holds the Mem0 admin/master key.

## Why a gateway instead of Hermes/OpenClaw talking to Mem0 directly

1. **Least privilege.** Mem0's admin key can read/write/delete everything
   across every namespace. Giving it to two independent agent codebases
   doubles the blast radius of a leak. The gateway holds it once, behind
   per-client keys scoped to one identity each.
2. **Policy enforcement.** Mem0's own filtering is whatever the pinned
   version happens to support. The gateway re-checks every read against
   `agent_id`/`project_id`/`memory_class`/`status` server-side (see
   `gateway/app/policy.py`), so a Mem0 version change or filter bug can't
   silently leak one agent's private memory to another.
3. **A single place to add auth, rate limiting, sensitive-data filtering,
   and audit logging** without touching Hermes or OpenClaw internals.
4. **Independent rollback.** If Mem0 misbehaves, the gateway can be
   stopped/rolled back without touching Hermes or OpenClaw at all — see
   `docs/hermes-integration.md` "Rollback".

## Namespace model

Every stored memory carries this metadata (stamped by the gateway, never
trusted from the client — see `gateway/app/policy.py::build_write_metadata`):

```json
{
  "user_id": "ngocviet-owner",
  "app_id": "ngocviet-ai-business-os",
  "agent_id": "hermes",
  "memory_class": "shared",
  "project_id": "global",
  "domain": "business",
  "sensitivity": "internal",
  "status": "active"
}
```

`agent_id` and `app_id` are derived purely from the caller's API key
(`config.py::client_registry`). A client that tries to set them in a
request body gets a 422 (Pydantic `extra="forbid"`, see `schemas.py`) —
not a silent override, so a misbehaving client fails loudly instead of
quietly succeeding with a different identity than it thought.

## Memory classes and visibility

| Class | Who can read it |
|---|---|
| `shared` | Any authenticated client (subject to future per-class ACL if needed) |
| `agent_private` | Only the agent that created it |
| `project` | Any client, but only when the search request's `project_id` matches the memory's `project_id` |
| `temporary` | Only the creating agent, and only until `expires_at` (TTL) |

Visibility is enforced twice: once as a best-effort filter passed to Mem0's
`/search`, and again unconditionally in the gateway
(`policy.py::filter_search_results`) before any result is returned. The
second check is the one that actually matters for security — the first is
just an optimization to reduce over-fetching.

## Data flow

**Write:** `client → POST /v1/memory/add → sensitive-data filter → policy
stamps agent_id/app_id/created_by/memory_class metadata → Mem0 POST
/memories → Postgres`

**Read:** `client → POST /v1/memory/search → Mem0 POST /search (best-effort
filtered) → gateway re-filters by policy → top `limit` results → client`

## Deployment topology

- Docker network `ngocviet-memory-net`, isolated from every other
  project's network (Odoo, n8n, etc. are untouched).
- `postgres` and `mem0` containers publish **no host ports** — reachable
  only from other containers on `ngocviet-memory-net`.
- `gateway` is the only container with a published port, bound to
  `127.0.0.1` by default (see `.env.example` `GATEWAY_BIND_HOST`).
- Named volume `ngocviet_mem0_postgres_data` — persistent, never removed by
  any script in this repo.

See `docs/deployment.md` for the phase-by-phase rollout and
`docs/security.md` for the full threat model.
