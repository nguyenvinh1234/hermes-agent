# hermes-adapter: memory_gateway plugin

A standalone Hermes plugin that gives Hermes three tools —
`memory_search`, `memory_add`, `memory_feedback` — backed by the NgocViet
Memory Gateway (`docs/api-contract.md` one level up).

## Why this isn't in `plugins/` in this repo

`plugins/AGENTS.md` closes `plugins/memory/` to new backends and forbids
new third-party-product plugins in-tree: they ship as standalone repos
installed under `~/.hermes/plugins/` or via a pip entry point. This
directory is written to be copied out that way, not merged into
`hermes-agent`'s own `plugins/` tree.

## Install

```bash
cp -r integrations/ngocviet-memory/hermes-adapter ~/.hermes/plugins/memory_gateway
pip install -r ~/.hermes/plugins/memory_gateway/requirements.txt
```

Set in whatever environment Hermes actually runs in (its own `.env` /
`~/.hermes/config`, **not** this subproject's `.env` — the plugin never
sees the Mem0 admin key, only its own gateway API key):

```
MEMORY_GATEWAY_URL=http://127.0.0.1:8077
MEMORY_GATEWAY_API_KEY=<value of MEMORY_GATEWAY_API_KEY_HERMES from the gateway's .env>
NGOCVIET_MEMORY_USER_ID=ngocviet-owner
```

Validate before relying on it:
```bash
hermes plugins doctor ~/.hermes/plugins/memory_gateway --ci
```

## What it does NOT do

- No `delete` tool — the gateway's `DELETE /v1/memory/{id}` is never
  called by this plugin.
- No unrestricted update — `memory_feedback` only ever sets `status` to
  `superseded` (outdated/contradicted) or leaves it `active` (confirmed);
  it never edits memory content.
- `user_id` is fixed via `NGOCVIET_MEMORY_USER_ID`, not an LLM-controllable
  argument — prevents a prompt-injected instruction from redirecting reads/
  writes into a different namespace.
- Never raises into the conversation turn: every gateway call is wrapped
  and degrades to "no memory" on any failure (see `client.py` and
  `tests/test_client.py`).

## Files

- `plugin.yaml` — plugin manifest (name, version, tools, required env).
- `__init__.py` — `register(ctx)`, tool schemas + handlers.
- `client.py` — HTTP calls to the gateway, all error handling.
- `tests/test_client.py` — graceful-degradation tests. Run with
  `pip install -r requirements.txt pytest && python -m pytest tests/ --import-mode=importlib`
  from this directory — the explicit `--import-mode=importlib` is required
  because this directory's name (`hermes-adapter`) isn't a valid Python
  identifier, which confuses pytest's default package-import resolution
  when no ini/config file sits next to `__init__.py`. Do not add a
  `pytest.ini`/`pyproject.toml` `[tool.pytest.ini_options]` block directly
  in this directory — that combination was found to break collection even
  more (it makes pytest try to import `__init__.py` itself as a bare
  module). Configure pytest from a parent directory instead if you need ini
  options.

## Verify before production use

This was written against the plugin convention documented at
`website/docs/developer-guide/plugins/index.md` in this repo, not against
a live Hermes runtime (this build session didn't run Hermes itself). Run
`hermes plugins doctor` and a real smoke conversation
(`docs/hermes-test-cases.md`) before trusting it.
