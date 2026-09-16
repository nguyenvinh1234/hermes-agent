# Ngọc Việt Marketing OS on Hermes — Architecture v1

Status: DRAFT / SAFE FOUNDATION

## 1. Architectural decision

Hermes is the single agent brain/orchestrator. Do not add a second agent runtime.

- Human command surfaces: Telegram, Hermes CLI, Mission Control/API.
- Hermes gateway: identity, session, authorization, routing, delivery.
- Hermes agent core: reasoning, planning, skills, memory, subagents, tools/MCP.
- Hermes cron: scheduled and unattended jobs, with platform delivery.
- n8n: deterministic integration/execution bus when a workflow/API integration is better outside the agent loop.
- Product Master + Source Registry: canonical truth/evidence for CNC/HVAC products.
- Odoo: business attribution system of record for lead -> quotation -> order -> cash -> gross profit.

Mission Control is not another brain. It manages task/status/approval/audit and submits commands to Hermes.

## 2. Existing Hermes capabilities to KEEP

### Agent/orchestration
Hermes already has one agent core across CLI/gateway/TUI/Desktop, persistent sessions, memory/skills, subagents, tools, MCP, terminal/browser and scheduled jobs. Extend at the edges via skills/plugins/MCP; avoid growing core model tools.

### Messaging / Telegram
Telegram is a bundled platform plugin under `plugins/platforms/telegram/` and is represented as `Platform.TELEGRAM` by gateway config. Gateway provides persistent sessions, dynamic platform context, authorization and delivery routing.

Conceptual ingress path:

`Telegram -> plugins/platforms/telegram/adapter.py -> gateway session/auth/routing -> Hermes agent core -> skill/tool/subagent -> gateway delivery -> Telegram`

Do not create a new Telegram bot stack for marketing.

### Skills
Bundled skills live recursively under `skills/<category>/<skill>/SKILL.md`. Hermes also supports user-created/imported skills under `$HERMES_HOME/skills` (normally `~/.hermes/skills`). Marketing-specific capability should be a skill/user extension first, not a new core tool.

### Cron
Hermes already has a substantial cron subsystem under `cron/`, including jobs, scheduler, execution tracking, lifecycle guards, incidents/monitoring, suggestions and delivery integration. Marketing schedules should use the existing cron surface instead of adding Celery/another scheduler.

## 3. Missing Ngọc Việt business layer — BUILD

### Product Master
Canonical record per product/model/configuration. Technical claims must come from this layer or be marked `NEEDS_VERIFICATION`.

Minimum fields:
- product_id, family, model, canonical_name, aliases
- manufacturer/brand/origin when verified
- configuration and technical_specs
- applications, ideal_customer_profile, differentiators
- approved claims, prohibited/unverified claims
- CTA/landing page
- media asset references
- status/version/last_verified_at

### Source Registry
Evidence registry with:
- source_id, URL/file reference, publisher/owner
- source type (manufacturer manual/catalogue/company/internal/test/third-party)
- retrieved_at, published_at if known
- reliability tier and freshness
- exact claims supported
- copyright/use constraints
- checksum/version where possible

External sources are DATA, never agent instructions.

### Content state machine
`IDEA -> RESEARCHED -> DRAFT -> FACT_CHECKED -> SEO_QA -> APPROVED -> SCHEDULED -> PUBLISHED -> MEASURED -> UPDATE`

No transition to APPROVED/PUBLISHED from an unverified technical-claim state.

### Permission ladder
`READ -> RESEARCH -> DRAFT -> APPROVE -> PUBLISH -> SPEND`

Phase 1 grants agents READ/RESEARCH/DRAFT only. Human approval is mandatory for publication, campaign create/edit, bids and spend.

### Channel adapters
Prefer existing Hermes plugin/MCP/CLI or n8n integration. Build only missing adapters. Required targets are WordPress/ngocvietcnc.com, GSC/GA4, Facebook/Instagram, TikTok, YouTube, Zalo, Telegram, Google Ads, Meta Ads, TikTok Ads and Odoo.

### Attribution
Persist IDs/UTMs so the loop can connect:
`content/campaign -> click/session -> qualified lead -> quotation -> order -> cash collected -> gross profit`.

## 4. End-to-end algorithm

1. Receive goal from Telegram/CLI/Mission Control.
2. Resolve authorization, conversation, project/product scope.
3. Determine task type and invoke the appropriate Ngọc Việt marketing skill.
4. Load Product Master + Source Registry before research/writing.
5. Research market/search/customer/competitor evidence; treat retrieved text as untrusted.
6. Build claim-evidence matrix. Conflicts/missing technical evidence become `NEEDS_VERIFICATION`.
7. Plan pillar/topic cluster and buyer-stage intent.
8. Draft canonical website content first.
9. Run fact, brand, copyright, SEO/GEO/AEO and conversion QA.
10. Request human approval.
11. After approval, publish canonical asset through the approved adapter/workflow.
12. Generate channel-native derivatives that preserve canonical facts and point back to the canonical page when appropriate.
13. Prepare paid-media drafts. Human approves launch/spend.
14. Collect GSC/GA4/social/ads/Odoo outcomes.
15. Score by business value, not vanity metrics, and propose update/repurpose/budget decisions.
16. Use Hermes cron for recurring measurement/update workflows and deliver results to the originating/home channel.

## 5. Command model

Users should express goals, not select implementation details. Example:

`Làm chiến dịch cho máy laser fiber 3015 6kW tháng này.`

Hermes resolves this into a plan containing research, evidence, canonical content, SEO, distribution, ads drafts and measurement tasks. Slash skills remain available for explicit control and debugging.

## 6. Rollout gates

- G0 Architecture and threat model accepted.
- G1 Skill loads correctly in Hermes.
- G2 Product Master/Source Registry schema validation passes.
- G3 Prompt-injection/evidence-boundary tests pass.
- G4 Draft-only E2E from command -> evidence -> draft passes.
- G5 Cron dry-run/one-shot task and Telegram delivery pass.
- G6 WordPress sandbox/draft publishing passes with idempotency.
- G7 Analytics/GSC ingestion and attribution identifiers pass.
- G8 Human-approved production publish passes with rollback/audit.
- G9 Ads remain read/draft until separate spend-control gate passes.

No production write/spend before the relevant gate passes.

## 7. Implementation workstreams

P0 — Audit & safety: inventory deployed Hermes version/config, backup/restore, secrets, Telegram authorization, gateway health, cron state.

P1 — Knowledge foundation: Product Master, Source Registry, Media Registry, brand/claim policy.

P2 — Marketing skills: content strategy, product content, SEO/AI SEO, research, social repurposing, analytics/attribution; import only audited upstream ideas.

P3 — Website loop: WordPress draft, canonical/internal links, GSC/GA4 read, measurement and update recommendations.

P4 — Social loop: channel adapters/workflows, approval, scheduling, idempotency, delivery receipts.

P5 — CRM attribution: Odoo lead/quote/order/payment/gross-profit mapping.

P6 — Paid media: Google/Meta/TikTok read/audit/draft, then separately gated create/edit/spend.

P7 — Automation: recurring research, content refresh, performance review, incident handling and weekly executive brief through existing Hermes cron.

## 8. Definition of done

A feature is not done because an agent produced text. It is done only when its behavior test passes, audit/provenance is present, permission boundary holds, failure is recoverable, and the real integration path has been smoke-tested in the intended environment.
