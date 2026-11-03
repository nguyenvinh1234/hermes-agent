"""Task-delegation tools for ``hermes mcp serve``: hand work to Hermes from any MCP client.

A remote assistant (ChatGPT / Claude on a phone, Claude Code, Cursor) files a task on the
Kanban board; the dispatcher embedded in the gateway spawns the assigned profile to do it,
and the assistant checks back with ``tasks_get``. Kanban is the existing durable work queue,
so delegation adds no new runtime: the MCP call returns in milliseconds while the work runs
for as long as it needs (no client tool-call timeout to fight).
"""

from __future__ import annotations

import json
from typing import Optional

_SUMMARY_FIELDS = ("id", "title", "status", "assignee", "priority", "created_at", "completed_at")
_DETAIL_FIELDS = _SUMMARY_FIELDS + ("body", "result", "last_failure_error", "created_by")
_RECENT_COMMENTS = 10
_CREATED_BY = "mcp"


def _default_assignee() -> str:
    """The profile serving MCP does the work; a non-profile HERMES_HOME falls back to default."""
    try:
        from hermes_cli.profiles import get_active_profile_name
        name = get_active_profile_name()
    except Exception:
        return "default"
    return "default" if name in ("", "custom") else name


def _fields(task, names) -> dict:
    return {name: getattr(task, name, None) for name in names}


def _dispatcher_warning() -> Optional[str]:
    """Human guidance when nothing will pick the task up, else None."""
    from hermes_cli.kanban import _check_dispatcher_presence

    running, message = _check_dispatcher_presence()
    return None if running else message


def tasks_create(title: str, details: str = "", assignee: Optional[str] = None, priority: int = 0) -> str:
    """Assign a new task to Hermes Agent. Hermes works on it in the background.

    Use this whenever the user asks Hermes to do something ("ask Hermes to ...",
    "giao việc cho Hermes ..."). Put everything Hermes needs in ``details``: the
    goal, inputs, constraints and what "done" looks like. The call returns at once
    with a task id; check progress and the final result later with tasks_get.

    Args:
        title: Short summary of the task
        details: Full instructions for Hermes (goal, context, expected output)
        assignee: Hermes profile that should do the work (default: this server's profile)
        priority: Higher runs first (default 0)
    """
    if not title or not title.strip():
        return json.dumps({"error": "title is required"})
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc

    try:
        with kbc.connect_closing() as conn:
            task_id = kb.create_task(
                conn, title=title.strip(), body=(details or "").strip() or None,
                assignee=(assignee or "").strip() or _default_assignee(),
                created_by=_CREATED_BY, priority=int(priority or 0))
            task = kb.get_task(conn, task_id)
    except (ValueError, TypeError) as e:
        return json.dumps({"error": str(e)})
    out = {"task": _fields(task, _SUMMARY_FIELDS)}
    if task.status == "ready":
        warning = _dispatcher_warning()
        if warning:
            out["warning"] = warning
    return json.dumps(out, indent=2, ensure_ascii=False)


def tasks_list(status: Optional[str] = None, limit: int = 20) -> str:
    """List tasks on the Hermes board, newest first.

    Args:
        status: Optional filter: triage, todo, scheduled, ready, running, blocked, review, done
        limit: Maximum number of tasks to return (default 20, max 100)
    """
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    from mcp_serve import _coerce_int

    limit = _coerce_int(limit, default=20, minimum=1, maximum=100)
    try:
        with kbc.connect_closing() as conn:
            rows = kb.list_tasks(conn, status=status or None, limit=limit, order_by="created-desc")
    except ValueError as e:
        return json.dumps({"error": str(e)})
    tasks = [_fields(t, _SUMMARY_FIELDS) for t in rows]
    return json.dumps({"count": len(tasks), "tasks": tasks}, indent=2, ensure_ascii=False)


def tasks_get(task_id: str) -> str:
    """Get a task's status, final result and latest comments.

    A task is finished when status is "done" (read ``result``); "blocked" means
    Hermes needs input — answer with tasks_comment.

    Args:
        task_id: The id returned by tasks_create or tasks_list
    """
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc

    with kbc.connect_closing() as conn:
        task = kb.get_task(conn, task_id)
        if task is None:
            return json.dumps({"error": f"Task not found: {task_id}"})
        comments = kb.list_comments(conn, task_id)[-_RECENT_COMMENTS:]
    return json.dumps({
        "task": _fields(task, _DETAIL_FIELDS),
        "comments": [{"author": c.author, "body": c.body, "created_at": c.created_at} for c in comments],
    }, indent=2, ensure_ascii=False)


def tasks_comment(task_id: str, text: str) -> str:
    """Add a note or follow-up instruction to a task.

    Commenting on a "blocked" task answers its question and puts it back in the
    queue (same as ``hermes kanban unblock --reason``).

    Args:
        task_id: The task to comment on
        text: The note for Hermes
    """
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc

    with kbc.connect_closing() as conn:
        task = kb.get_task(conn, task_id)
        if task is None:
            return json.dumps({"error": f"Task not found: {task_id}"})
        try:
            comment_id = kb.add_comment(conn, task_id, _CREATED_BY, text)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        unblocked = task.status == "blocked" and kb.unblock_task(conn, task_id)
    return json.dumps({"ok": True, "task_id": task_id, "comment_id": comment_id, "unblocked": bool(unblocked)})


TASK_TOOLS = (tasks_create, tasks_list, tasks_get, tasks_comment)
