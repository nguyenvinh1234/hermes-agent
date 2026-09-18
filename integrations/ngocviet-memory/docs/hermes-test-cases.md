# Hermes Memory Test Cases

35 cases across the groups required by the rollout spec (section 24). This
is a **test plan**, not a report — no test here has actually been run
against a live Hermes+gateway (this build session had neither running).
Run these in Phase 6 (`docs/deployment.md`) and record real outcomes in a
new `docs/hermes-test-report.md`, one row per case, `PASS`/`FAIL` plus what
actually happened — never mark a case PASS without having run it.

Each case: a setup turn, a later probe turn (often "a new session" to test
persistence across sessions, not just within-context recall), and what a
correct Hermes response looks like.

## Company fact (3)

1. **Setup:** "Odoo is the operational source of truth for the company."
   **Probe (new session):** "What system is our operational source of
   truth?" **Expect:** recalls Odoo correctly.
2. **Setup:** "Obsidian is our knowledge layer." **Probe:** "Where do we
   keep our knowledge base?" **Expect:** recalls Obsidian.
3. **Setup:** "Ngoc Viet AI Business OS is the umbrella project name."
   **Probe:** "What's the name of the overall project?" **Expect:**
   recalls correctly.

## System architecture (3)

4. **Setup:** "Hermes is the central orchestration hub." **Probe (new
   session):** "Hermes có vai trò gì?" **Expect:** recalls "orchestration
   hub" even though the probe is in Vietnamese and the setup was in
   English (semantic recall, not string match).
5. **Setup:** "OpenClaw handles agent runtime and sales workflows."
   **Probe:** "What does OpenClaw do?" **Expect:** recalls both runtime and
   sales workflow roles.
6. **Setup:** "The memory gateway is the only thing allowed to talk to
   Mem0 directly." **Probe:** "Can Hermes call Mem0 directly?" **Expect:**
   answers no, cites the gateway.

## User preference (3)

7. **Setup:** "I prefer responses in Vietnamese by default." **Probe (new
   session, ambiguous-language question):** Hermes should lean Vietnamese
   unless context says otherwise.
8. **Setup:** "Always confirm before deploying to production." **Probe:**
   Ask Hermes to deploy something. **Expect:** it asks for confirmation
   first, citing the stored preference if asked why.
9. **Setup:** "Keep answers short unless I ask for detail." **Probe:** a
   simple factual question. **Expect:** a short answer.

## Project decision (3)

10. **Setup:** "We decided to use PostgreSQL + pgvector for agent memory,
    not a standalone vector DB." **Probe:** "What DB backs agent memory?"
    **Expect:** correct recall.
11. **Setup:** "The gateway repo lives under `integrations/ngocviet-memory/`
    inside hermes-agent, not a separate repo, for now." **Probe:** "Where's
    the memory gateway code?" **Expect:** correct path.
12. **Setup:** "OpenClaw integration is on hold until Hermes passes all
    tests." **Probe:** "Can we start OpenClaw integration now?" **Expect:**
    Hermes says no / not yet, citing the gate.

## Technical constraint (3)

13. **Setup:** "Gateway search must respond in under 1 second under normal
    load." **Probe:** "What's the latency budget for memory search?"
    **Expect:** recalls the number.
14. **Setup:** "Never give Hermes the Mem0 admin key." **Probe:** "Should
    Hermes hold the Mem0 admin key?" **Expect:** no.
15. **Setup:** "Rate limit is 60 requests per minute per client." **Probe:**
    "What's our rate limit?" **Expect:** correct recall.

## Repeated memory / dedup (3)

16. Say "Hermes is the orchestration hub" in session A, then "Hermes acts
    as the main orchestrator" (same fact, different phrasing) in session
    B. **Expect:** search later returns this fact once (or as a clearly
    related pair), not N unbounded duplicates as this gets repeated across
    many sessions.
17. Say the exact same sentence verbatim in three different sessions.
    **Expect:** memory store doesn't balloon 1:1 with repetition — verify
    against your pinned Mem0's actual dedup behavior (checked in Phase 2).
18. Store a preference, then have Hermes "confirm" recalling it correctly
    (`memory_feedback(..., "confirmed")`). **Expect:** no new duplicate
    memory created by the confirmation itself.

## Contradictory memory (3)

19. **Setup A:** "OpenClaw is the central orchestrator." Later, **Setup
    B:** "Correction: Hermes is now the central orchestrator." **Probe:**
    "Who is the central orchestrator?" **Expect:** answers Hermes (the
    newer fact), and a check of the memory store shows the old one's
    `status` moved to `superseded`, not silently coexisting as equally
    "active".
20. Two contradictory technical constraints stated a week apart (simulate
    via direct `memory_add` timestamps if needed). **Expect:** the more
    recent one wins in recall, the older one is superseded not deleted
    (auditable).
21. A contradiction inside the *same* session (user corrects themselves
    immediately). **Expect:** Hermes uses the correction for the rest of
    that session even before any write-flow triage runs (this is normal
    in-context behavior, not a memory-system requirement — included here
    to make sure the memory write afterward doesn't re-introduce the
    stale fact).

## Sensitive information (3)

22. User pastes a fake-but-realistic API key into chat mid-conversation.
    **Expect:** the write-flow triage does not propose storing it, and
    even if it did, the gateway's sensitive-data filter rejects the
    `memory_add` call (400) — verify both layers independently.
23. User says "my password is correct-horse-battery-staple." **Expect:**
    same as above — rejected, not stored.
24. A tool-call log containing a `Bearer ...` header ends up in
    conversation context. **Expect:** the write-flow triage never proposes
    raw tool logs as memory candidates in the first place (this is a
    triage-quality case, not just a filter case).

## Temporary information (3)

25. "Remind yourself the deploy window is paused until Friday" (clearly
    time-bound). **Expect:** stored as `memory_class=temporary` with a
    sensible TTL, not `shared`/permanent.
26. Probe for the same fact after the TTL has passed (simulate by setting
    a short `ttl_seconds` in a direct test call). **Expect:** no longer
    returned by search.
27. Probe for the same fact while still within the TTL. **Expect:**
    returned normally.

## Project isolation (3)

28. Store a decision under `project_id=obsidian`. Probe with
    `project_id=mach3-turret`. **Expect:** not returned (see gateway test
    `test_project_isolation_between_projects` for the equivalent
    gateway-level check already automated in
    `gateway/tests/test_memory_routes.py`).
29. Store a decision under `project_id=obsidian`, probe with
    `project_id=obsidian`. **Expect:** returned.
30. Store a `shared`-class fact with no specific project relevance
    (`project_id=global`). Probe under any `project_id`. **Expect:**
    gateway behavior here depends on whether `shared` should be
    project-scoped too — current implementation does **not** scope
    `shared` by project (see `gateway/app/policy.py::is_visible`); confirm
    this matches actual intent during Phase 6 and adjust policy.py if not.

## Agent isolation (3)

31. Hermes stores an `agent_private` memory. Query as if OpenClaw (once
    OpenClaw's key exists) or via `curl` with the OpenClaw key directly.
    **Expect:** not visible (already covered at the gateway level by
    `test_agent_private_isolated_between_hermes_and_openclaw` — this case
    re-verifies it through the actual Hermes conversational path).
32. Hermes stores a `shared` memory. Query with the OpenClaw key.
    **Expect:** visible.
33. Attempt (via a crafted tool call, not normal usage) to make the
    adapter send `agent_id: "openclaw"` in a `memory_add` call while
    authenticated as Hermes. **Expect:** 422 from the gateway; the plugin
    should never construct such a payload in the first place, but this
    confirms the gateway doesn't trust it either way.

## Semantic recall (2)

34. Store "The company uses Hermes as orchestration hub" in English. Probe
    in Vietnamese: "Hermes làm nhiệm vụ gì trong hệ thống?" **Expect:**
    correct semantic recall across languages.
35. Store a fact using one phrasing ("we decided to pin container image
    versions instead of using `latest`"). Probe using a paraphrase ("do we
    use floating Docker tags or pinned ones?"). **Expect:** correct
    semantic recall despite no shared keywords beyond "docker"/"tags".

## Pass criteria (section 19/37)

- 100% of the 35 cases behave as expected, or every deviation is logged
  with a root cause in `docs/hermes-test-report.md`.
- No 5xx from the gateway during the run.
- No secret ever appears in a stored memory or in logs.
- Namespace/project/agent isolation cases (28–33) all pass without
  exception — these are the security-critical ones; a failure here blocks
  Phase 7 regardless of how the rest score.
