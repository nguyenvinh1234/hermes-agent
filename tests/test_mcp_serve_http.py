"""Remote MCP access (`hermes mcp serve --http`) and task delegation over MCP.

Contracts: only the capability URL ``/mcp/<token>`` or ``/mcp`` + matching bearer reaches the
MCP app (and it sees its own ``/mcp`` path); a task created over MCP lands on the real kanban
board assigned to the serving profile, and answering a blocked task re-queues it.
"""
from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp", reason="MCP SDK not installed")
httpx = pytest.importorskip("httpx")


def _call(server, name, args):
    result = asyncio.run(server.call_tool(name, args))
    return json.loads("".join(b.text for b in result.content if getattr(b, "text", None)))


def test_token_gate_admits_only_capability_url_or_bearer():
    from mcp_serve_http import TokenGate

    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    token = "s3cret-token"
    app = TokenGate(inner, token)

    async def status(path, headers=None):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://tunnel.example") as c:
            return (await c.post(path, headers=headers or {})).status_code

    async def run():
        return {
            "capability": await status(f"/mcp/{token}"),
            "bearer": await status("/mcp", {"Authorization": f"Bearer {token}"}),
            "wrong_token": await status("/mcp/nope"),
            "no_auth": await status("/mcp"),
            "wrong_bearer": await status("/mcp", {"Authorization": "Bearer nope"}),
            "token_prefix": await status(f"/mcp/{token[:-1]}"),
            "oauth_probe": await status("/.well-known/oauth-protected-resource"),
        }

    codes = asyncio.run(run())
    assert codes["capability"] == codes["bearer"] == 200
    assert {codes[k] for k in codes if k not in ("capability", "bearer")} == {404}
    assert seen == ["/mcp", "/mcp"]


def test_task_delegation_lands_on_board_and_comment_unblocks(monkeypatch):
    import mcp_serve
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    from hermes_cli import kanban as kanban_cli

    monkeypatch.setattr(kanban_cli, "_check_dispatcher_presence", lambda hermes_home=None: (True, ""))
    server = mcp_serve.create_mcp_server(event_bridge=mcp_serve.EventBridge())

    created = _call(server, "tasks_create", {"title": "Tóm tắt email", "details": "Đọc inbox"})["task"]
    with kbc.connect_closing() as conn:
        row = kb.get_task(conn, created["id"])
        blocked_id = kb.create_task(conn, title="needs input", assignee="default", initial_status="blocked")
    assert (row.title, row.body, row.assignee, row.status) == ("Tóm tắt email", "Đọc inbox", "default", "ready")
    assert _call(server, "tasks_get", {"task_id": created["id"]})["task"]["id"] == created["id"]

    reply = _call(server, "tasks_comment", {"task_id": blocked_id, "text": "use the Q3 numbers"})
    with kbc.connect_closing() as conn:
        task = kb.get_task(conn, blocked_id)
        comments = [c.body for c in kb.list_comments(conn, blocked_id)]
    assert reply["unblocked"] is True and task.status != "blocked"
    assert "use the Q3 numbers" in comments
