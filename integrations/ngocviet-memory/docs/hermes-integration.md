# Hermes Integration

Only start this after Mem0, Gateway, and Backup/Restore all PASS (Phases
1–4 in `docs/deployment.md`).

## Adapter, not core

Hermes is integrated via a standalone plugin
(`integrations/ngocviet-memory/hermes-adapter/`), installed under
`~/.hermes/plugins/memory_gateway/` (or as a pip entry point) — **no file
under this repo's own `run_agent.py`, `cli.py`, `gateway/`, or
`toolsets.py` is modified.** This follows `plugins/AGENTS.md`'s policy that
new memory-backend integrations ship as standalone plugin repos, not
in-tree additions, and Hermes' own convention that a plugin registers
tools via `ctx.register_tool(...)` rather than touching core.

## The three tools

1. **`memory_search(query, limit=8, memory_class=["shared","agent_private"], project_id=None)`**
   → calls `POST /v1/memory/search`. Read-only.
2. **`memory_add(content, memory_class="agent_private", project_id="global", domain="general")`**
   → calls `POST /v1/memory/add`. Content still passes through the
   gateway's sensitive-data filter regardless of what the plugin sends.
3. **`memory_feedback(memory_id, feedback_type, note=None)`** where
   `feedback_type` is one of `confirmed | outdated | contradicted` → maps
   to `PATCH /v1/memory/{id}` (`outdated`/`contradicted` set
   `status=superseded`; `confirmed` is a light touch that leaves status
   `active`). This is how Hermes marks a memory as no longer current
   without deleting it (section 26, contradiction handling).

**No delete tool is registered.** `MEMORY_GATEWAY_API_KEY_HERMES` can call
`DELETE /v1/memory/{id}` at the gateway HTTP layer (an OpenClaw/admin
capability exists there), but the Hermes plugin's `register()` simply never
wires it up — Hermes has no code path that can invoke it.

## Recall flow (before the LLM call)

```
User message
  → memory_search(query=<user message or a short reformulation>, limit=5..10)
  → format results as:

    [MEMORY CONTEXT]
    1. <memory text>
    2. <memory text>
    ...
    [/MEMORY CONTEXT]

  → prepend/inject into the LLM context
  → normal LLM call
```

`limit` stays in the 5–10 range (`top_k`) — never dump the whole store into
the prompt. If `memory_search` errors or times out, treat the result as
empty and continue the LLM call unmodified (see "Rollback / failure modes"
below) — memory is an enhancement, not a dependency.

## Write flow (after the conversation turn)

```
Conversation turn
  → memory triage (LLM or rule-based candidate extraction — conservative:
    prefer false negatives over false positives, per section 23)
  → candidate facts only: preferences, decisions, architecture decisions,
    technical constraints, business facts, SOP, project status, lessons
    learned, resolved bugs, important config decisions
  → NEVER: small talk, tool logs, stack traces, terminal dumps, raw
    prompts, anything that looks like a credential (the gateway's
    sensitive-data filter is a second line of defense, not the only one —
    the triage step should already be filtering these out)
  → memory_add(...) per candidate, with the narrowest memory_class that
    makes sense (default agent_private unless the fact is clearly meant to
    be shared across agents)
```

## Duplicate and contradiction handling

- Mem0's own update/dedup behavior handles near-duplicate phrasing of the
  same fact at the Mem0 layer (verify this against your pinned commit in
  Phase 2 — do not assume it works a specific way without checking).
  `memory_feedback(..., "confirmed")` lets Hermes reinforce a fact it
  recalled correctly without creating a new duplicate memory.
- When Hermes recalls a memory that a later turn clearly contradicts
  (e.g. "OpenClaw is the central orchestrator" vs. a new "Hermes is now
  the central orchestrator"), call `memory_feedback(old_id, "contradicted")`
  to mark the old one `superseded` before/alongside adding the new one via
  `memory_add`. Superseded memories are excluded from search results by
  the gateway automatically (`policy.py::is_visible`), so no extra
  filtering is needed on the Hermes side.

## Rollback / failure modes

- Disabling the adapter (remove/rename the plugin directory, or unset
  `MEMORY_GATEWAY_API_KEY` in Hermes' env) returns Hermes to its prior
  behavior exactly — no core file was ever touched.
- If the gateway is unreachable, times out, or returns 5xx: `memory_search`
  returns an empty result list and `memory_add`/`memory_feedback` no-op,
  each logging a warning. **The conversation must never hard-fail because
  memory is down** — this is the adapter's responsibility to guarantee
  (wrap every gateway HTTP call in try/except with a short timeout, per
  the adapter's own `client.py`).
- Wrong API key, invalid payload, or a rejected secret all surface as a
  normal tool error the LLM sees and can react to conversationally — none
  of these should crash the turn either.

## What Hermes never gets

- The Mem0 admin key.
- Direct Postgres access.
- Another agent's `agent_private`/`project`/`temporary` memories (enforced
  gateway-side, not by adapter convention).
- A delete capability.

See `docs/hermes-test-cases.md` for the test matrix to run once this is
wired up, and `docs/deployment.md` Phase 6 for how to record results.
