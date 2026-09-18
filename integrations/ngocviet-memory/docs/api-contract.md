# API Contract — NgocViet Memory Gateway

Base URL: `http://<GATEWAY_BIND_HOST>:<GATEWAY_BIND_PORT>` (default
`http://127.0.0.1:8077`, internal-only unless you put a reverse proxy with
its own auth in front — see `docs/security.md`).

Auth: every `/v1/memory/*` route requires `X-NgocViet-API-Key: <key>`.
`/health` does not require auth; `/ready` does not require auth either
(both are meant for internal healthchecks/monitoring, not for callers who
need memory data).

## Multi-client by design

This is the one contract every caller shares — Hermes and OpenClaw today,
and n8n, DeepSeek Harness, or Codex later, all speak the exact same
`/v1/memory/*` routes and request/response shapes. Onboarding a new client
never changes this contract: it's a `.env` change on the gateway side
(`MEMORY_GATEWAY_CLIENT_IDS` + a new `MEMORY_GATEWAY_API_KEY_<ID>`, see
`.env.example`) plus that client getting its own key and calling the same
routes below with its own `X-NgocViet-API-Key`. `agent_id` in stored
metadata is always the calling client's id — so e.g. an n8n workflow's
writes show up as `agent_id: "n8n"`, visible to itself as `agent_private`
and to everyone as `shared`, exactly like Hermes/OpenClaw today. Routes are
versioned under `/v1/` so a future breaking change ships as `/v2/` without
disrupting existing callers.

## GET /health

Process-liveness only. Always `{"status": "ok"}` with HTTP 200 if the
gateway process is up, regardless of Mem0/Postgres state.

## GET /ready

Checks the full chain: gateway → Mem0 → Postgres (Mem0's own DB
connectivity, via a lightweight probe query since Mem0 has no dedicated
health endpoint — see `gateway/app/mem0_client.py::probe_db`).

```json
{
  "ready": false,
  "components": {"gateway": true, "mem0": true, "postgres": false}
}
```

HTTP 200 when `ready: true`, HTTP 503 otherwise.

## POST /v1/memory/add

```json
{
  "user_id": "ngocviet-owner",
  "content": "Hermes là orchestrator trung tâm.",
  "memory_class": "shared",
  "project_id": "global",
  "domain": "architecture",
  "sensitivity": "internal",
  "supersedes": null,
  "ttl_seconds": null
}
```

- `memory_class` defaults to `agent_private` if omitted (conservative —
  never default to `shared`).
- `project_id`/`domain`/`sensitivity` default to `"global"`/`"general"`/`"internal"`.
- `ttl_seconds` only meaningful (and only honored) when `memory_class ==
  "temporary"`; otherwise ignored.
- Sending `agent_id`, `app_id`, or `created_by` in the body → **422**, the
  gateway injects these itself from the API key.
- Content matching a known secret pattern (private key block, `sk-...`,
  `Bearer ...`, `ghp_...`, etc.) → **400**, nothing is stored.

Response `201`:
```json
{"id": "abc123", "status": "created"}
```

## POST /v1/memory/search

```json
{
  "user_id": "ngocviet-owner",
  "query": "Hermes có vai trò gì?",
  "limit": 8,
  "memory_class": ["shared", "agent_private"],
  "project_id": "global"
}
```

- `limit` max 50.
- `memory_class` defaults to `["shared", "agent_private"]` if omitted.
- Results are always filtered server-side to what the caller's `agent_id`
  is actually allowed to see (see `docs/architecture.md`); a client can
  never widen its own visibility by asking for more classes.

Response `200`:
```json
{
  "results": [
    {"id": "...", "memory": "...", "score": 0.91, "metadata": {}}
  ]
}
```

## GET /v1/memory/{memory_id}

Returns `404` both when the memory truly doesn't exist and when it exists
but the caller isn't allowed to see it — the response is intentionally
identical in both cases (no existence oracle for memories you can't read).

## PATCH /v1/memory/{memory_id}

```json
{"content": "updated text", "status": "superseded", "sensitivity": "internal"}
```

All fields optional. Only the memory's owning agent may update an
`agent_private`/`project`/`temporary` memory it did not create; `shared`
memories may be updated by any authenticated client (e.g. to mark one
superseded after a contradiction). New `content` is still run through the
sensitive-data filter. → `200 {"status": "updated"}`.

## DELETE /v1/memory/{memory_id}

Only the owning agent may delete. → `200 {"status": "deleted"}` or `403` if
not the owner, `404` if not found.

**The Hermes adapter (`integrations/ngocviet-memory/hermes-adapter/`) does
not expose delete to Hermes at all** — see `docs/hermes-integration.md`.
DELETE exists at the gateway HTTP layer for administrative/OpenClaw use.

## Error shape

Standard FastAPI error body: `{"detail": "..."}` (or a list of validation
errors for 422s). No internal stack traces, upstream Mem0 response bodies,
or secrets are ever included.

## Status codes summary

| Code | Meaning |
|---|---|
| 200/201 | success |
| 400 | secret detected in content, or other bad request |
| 401 | missing/invalid `X-NgocViet-API-Key` |
| 403 | authenticated, but not the owner of this memory |
| 404 | not found, or found-but-not-visible-to-you |
| 422 | schema violation, including an attempt to set `agent_id`/`app_id` |
| 429 | rate limit exceeded (per-client, see `.env.example`) |
| 502 | Mem0 returned an error |
| 503 | `/ready` only — dependency chain not healthy |
| 504 | Mem0 unreachable/timed out |
