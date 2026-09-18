# OpenClaw Integration Plan (assessment only — no production changes)

Per the rollout spec, this is a plan, not an implementation. Nothing here
touches OpenClaw production. It also cannot be fully completed yet: this
build session has no access to OpenClaw's actual codebase/deployment (it
only had the `hermes-agent` repo), so several sections below are marked
`<TO FILL IN>` — whoever does have access to OpenClaw needs to complete
them before Phase 7 can be considered done.

## Preconditions

Do not start real OpenClaw work until `docs/hermes-test-report.md`
(produced in Phase 6) says `PASS` or `PASS WITH WARNINGS` with no open
security findings.

## What needs to be assessed (against the real OpenClaw deployment)

1. **Current OpenClaw memory system** — does it have one today? File-based?
   A database? An existing vector store? `<TO FILL IN>`
2. **Existing Mem0 integration, if any** — is OpenClaw already using Mem0
   directly (its own instance, its own Postgres)? If so, that's a second
   independent memory database, which the target architecture explicitly
   forbids ("Không có hai memory databases độc lập") — this needs a
   migration plan, not just a new integration. `<TO FILL IN>`
3. **Current plugins/extension points** — does OpenClaw have an equivalent
   of Hermes' `register(ctx)` plugin system, or would integration mean
   editing OpenClaw core? `<TO FILL IN>`
4. **Current memory files/db location(s)** — paths, formats, approximate
   size, last-write time. `<TO FILL IN>`
5. **Migration risk** — if OpenClaw has existing memory data worth
   preserving, what's the risk of importing it into the shared Mem0 store
   under `agent_id=openclaw`? (Format mismatch, PII/secrets baked into old
   records that would now hit the gateway's sensitive-data filter, volume.)
   **Per section 34 of the rollout spec, do not auto-migrate this data
   without a separate, reviewed rollback plan** — this plan only identifies
   the risk, it does not authorize a migration.
6. **Adapter approach** — mirror the Hermes adapter pattern: a standalone
   client using `MEMORY_GATEWAY_API_KEY_OPENCLAW` (already provisioned in
   `.env.example`), calling the same `/v1/memory/*` contract
   (`docs/api-contract.md`). OpenClaw's own extension mechanism (once
   known from item 3) determines exactly how it's wired in.
7. **Rollback** — same shape as Hermes': disabling the OpenClaw adapter
   must return OpenClaw to its exact prior behavior. If OpenClaw currently
   has its own working memory system, do not remove or disable it until
   the gateway-backed path has independently passed the same test bar
   Hermes did (Phase 6 equivalent, run against OpenClaw).

## Target end state

```
OpenClaw → NgocViet Memory Gateway → Mem0 → PostgreSQL/pgvector
```

Same gateway, same Postgres, same namespace model as Hermes — `agent_id:
"openclaw"` scoping its `agent_private` memories, `shared` memories visible
to both agents, `project_id` isolating per-project data
(`docs/architecture.md`). No second Mem0 instance, no second Postgres.

## Explicitly not authorized by this document

- Any change to an OpenClaw production container, config, or database.
- Any automatic migration of existing OpenClaw memory data.
- Granting OpenClaw's gateway key anything beyond what Hermes' key has
  (same three-tool-equivalent shape, no delete, no admin key) unless a
  separate, explicit approval says otherwise.

## Next step

Have someone with real access to the OpenClaw deployment fill in the
`<TO FILL IN>` sections above, then this plan can be turned into an actual
Phase 7 implementation plan (still gated on Hermes PASS and separate
approval per the rollout spec's rule 9).
