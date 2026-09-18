"""Hermes plugin: memory_search / memory_add / memory_feedback.

Install as a standalone plugin (see README.md) — this package is
intentionally NOT part of hermes-agent's in-tree `plugins/` directory,
per `plugins/AGENTS.md`'s "no new in-tree memory providers / no new
third-party-product plugins" policy.

`register(ctx)` is the documented entry point
(`website/docs/developer-guide/plugins/index.md`, "general" plugin kind).
Verify `ctx.register_tool`'s exact signature against the Hermes version you
actually run before enabling this in production — it was written against
the convention reported in that guide, not against a live Hermes install.

user_id is intentionally NOT an LLM-controllable parameter: it comes from
NGOCVIET_MEMORY_USER_ID (default "ngocviet-owner") so a prompt-injected
instruction can't make the agent read/write another namespace by asking it
to.
"""
from __future__ import annotations

import json
import os

from . import client

DEFAULT_USER_ID = "ngocviet-owner"


def _user_id() -> str:
    return os.getenv("NGOCVIET_MEMORY_USER_ID", DEFAULT_USER_ID)


def _memory_search_handler(args: dict, **_kwargs) -> str:
    results = client.search(
        query=args.get("query", ""),
        user_id=_user_id(),
        limit=int(args.get("limit", 8)),
        memory_class=args.get("memory_class"),
        project_id=args.get("project_id"),
    )
    return json.dumps({"results": results}, ensure_ascii=False)


def _memory_add_handler(args: dict, **_kwargs) -> str:
    content = args.get("content", "")
    if not content.strip():
        return json.dumps({"status": "skipped", "reason": "empty content"})
    result = client.add(
        content=content,
        user_id=_user_id(),
        memory_class=args.get("memory_class", "agent_private"),
        project_id=args.get("project_id", "global"),
        domain=args.get("domain", "general"),
    )
    if result is None:
        return json.dumps({"status": "skipped"})
    return json.dumps({"status": "stored", "id": result.get("id")})


def _memory_feedback_handler(args: dict, **_kwargs) -> str:
    ok = client.feedback(
        memory_id=args.get("memory_id", ""),
        feedback_type=args.get("feedback_type", ""),
        note=args.get("note"),
    )
    return json.dumps({"status": "ok" if ok else "skipped"})


def _has_gateway_config() -> bool:
    return bool(os.getenv("MEMORY_GATEWAY_URL") and os.getenv("MEMORY_GATEWAY_API_KEY"))


def register(ctx) -> None:
    ctx.register_tool(
        name="memory_search",
        toolset="memory_gateway",
        schema={
            "name": "memory_search",
            "description": (
                "Search shared/private long-term memory before answering. "
                "Use for recalling prior decisions, preferences, architecture "
                "facts, or SOPs. Returns at most 10 results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to recall."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 8},
                    "memory_class": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["shared", "agent_private", "project", "temporary"]},
                    },
                    "project_id": {"type": "string"},
                },
                "required": ["query"],
            },
        },
        handler=_memory_search_handler,
        check_fn=_has_gateway_config,
    )

    ctx.register_tool(
        name="memory_add",
        toolset="memory_gateway",
        schema={
            "name": "memory_add",
            "description": (
                "Store a single long-term-value fact (preference, decision, "
                "architecture fact, SOP, resolved bug, project status). Do "
                "NOT use for small talk, logs, or anything resembling a "
                "credential/secret — those are rejected automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "memory_class": {
                        "type": "string",
                        "enum": ["shared", "agent_private", "project", "temporary"],
                        "default": "agent_private",
                    },
                    "project_id": {"type": "string", "default": "global"},
                    "domain": {"type": "string", "default": "general"},
                },
                "required": ["content"],
            },
        },
        handler=_memory_add_handler,
        check_fn=_has_gateway_config,
    )

    ctx.register_tool(
        name="memory_feedback",
        toolset="memory_gateway",
        schema={
            "name": "memory_feedback",
            "description": (
                "Mark a previously recalled memory as confirmed, outdated, "
                "or contradicted by newer information. Use 'contradicted' "
                "when the user states something that supersedes a recalled "
                "fact, instead of leaving both active."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "feedback_type": {"type": "string", "enum": ["confirmed", "outdated", "contradicted"]},
                    "note": {"type": "string"},
                },
                "required": ["memory_id", "feedback_type"],
            },
        },
        handler=_memory_feedback_handler,
        check_fn=_has_gateway_config,
    )
