#!/usr/bin/env python3
"""Odoo MCP server for odoo.ngocvietai.com (stdio transport, stdlib only).

Speaks the Model Context Protocol (newline-delimited JSON-RPC 2.0 on
stdin/stdout) and forwards tool calls to Odoo's external JSON-RPC API
(`/jsonrpc`, services `common` + `object`). No third-party packages are
needed, so the plugin works with any Python >= 3.8 on PATH.

Configuration (environment variables):
  ODOO_URL        default https://odoo.ngocvietai.com
  ODOO_DB         database name (required unless the server lists exactly one)
  ODOO_USERNAME   login (usually an email)
  ODOO_API_KEY    API key (Preferences -> Account Security -> New API Key);
                  ODOO_PASSWORD is accepted as a fallback
  ODOO_READ_ONLY  "1"/"true" hides create/write/unlink/call_method tools
  ODOO_TIMEOUT    HTTP timeout in seconds (default 60)
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import traceback
import urllib.error
import urllib.request

SERVER_NAME = "odoo-ngocvietai"
SERVER_VERSION = "0.1.0"
DEFAULT_URL = "https://odoo.ngocvietai.com"
SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_LIMIT = 80
MAX_LIMIT = 500
MAX_OUTPUT_CHARS = 120_000


class OdooError(Exception):
    """An error reported by Odoo or by the transport, shown to the model as-is."""


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


class OdooClient:
    def __init__(self, env: dict[str, str] | None = None):
        env = os.environ if env is None else env
        self.url = (env.get("ODOO_URL") or DEFAULT_URL).rstrip("/")
        self.db = env.get("ODOO_DB") or ""
        self.username = env.get("ODOO_USERNAME") or ""
        self.secret = env.get("ODOO_API_KEY") or env.get("ODOO_PASSWORD") or ""
        self.read_only = _truthy(env.get("ODOO_READ_ONLY"))
        self.timeout = float(env.get("ODOO_TIMEOUT") or 60)
        self.uid: int | None = None
        self._ids = itertools.count(1)
        self._binary_fields: dict[str, list[str]] = {}

    # -- transport -------------------------------------------------------
    def _post(self, path: str, params: dict) -> object:
        body = json.dumps(
            {"jsonrpc": "2.0", "method": "call", "params": params, "id": next(self._ids)}
        ).encode()
        req = urllib.request.Request(
            self.url + path,
            data=body,
            # A custom User-Agent is required: the odoo.ngocvietai.com WAF answers
            # 403 to Python's default "Python-urllib/x.y".
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"{SERVER_NAME}-mcp/{SERVER_VERSION}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise OdooError(f"HTTP {exc.code} from {self.url}{path}") from exc
        except urllib.error.URLError as exc:
            raise OdooError(f"Cannot reach {self.url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise OdooError(f"Non-JSON response from {self.url}{path}") from exc
        if payload.get("error"):
            err = payload["error"]
            data = err.get("data") or {}
            raise OdooError(data.get("message") or err.get("message") or json.dumps(err))
        return payload.get("result")

    def _service(self, service: str, method: str, *args) -> object:
        return self._post("/jsonrpc", {"service": service, "method": method, "args": list(args)})

    # -- session ---------------------------------------------------------
    def version(self) -> dict:
        return self._service("common", "version")

    def _resolve_db(self) -> str:
        if self.db:
            return self.db
        try:
            dbs = self._service("db", "list")
        except OdooError:
            dbs = None
        if isinstance(dbs, list) and len(dbs) == 1:
            self.db = dbs[0]
            return self.db
        raise OdooError(
            "ODOO_DB is not set and the server does not expose a single database. "
            "Set ODOO_DB to your database name (run /odoo-ngocvietai:setup for help)."
        )

    def login(self) -> int:
        if self.uid:
            return self.uid
        if not self.username or not self.secret:
            raise OdooError(
                "Missing credentials: set ODOO_USERNAME and ODOO_API_KEY "
                "(run /odoo-ngocvietai:setup for help)."
            )
        db = self._resolve_db()
        uid = self._service("common", "authenticate", db, self.username, self.secret, {})
        if not uid:
            raise OdooError(
                f"Authentication failed for {self.username!r} on database {db!r} at {self.url}."
            )
        self.uid = int(uid)
        return self.uid

    def execute(self, model: str, method: str, args: list | None = None, kwargs: dict | None = None):
        uid = self.login()
        return self._service(
            "object", "execute_kw", self.db, uid, self.secret, model, method, args or [], kwargs or {}
        )

    # -- helpers ---------------------------------------------------------
    def default_fields(self, model: str) -> list[str]:
        """All fields except binary ones (images/attachments bloat output)."""
        if model not in self._binary_fields:
            meta = self.execute(model, "fields_get", [], {"attributes": ["type"]})
            self._binary_fields[model] = [
                name for name, info in meta.items() if info.get("type") != "binary"
            ]
        return self._binary_fields[model]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_DOMAIN = {
    "type": "array",
    "description": (
        "Odoo search domain, e.g. [[\"is_company\",\"=\",true],[\"country_id.code\",\"=\",\"VN\"]]. "
        "Use \"|\" / \"&\" / \"!\" prefix operators for OR/AND/NOT. Empty list matches all."
    ),
    "items": {},
}
_MODEL = {"type": "string", "description": "Technical model name, e.g. res.partner, sale.order"}
_IDS = {"type": "array", "items": {"type": "integer"}, "description": "Record IDs"}
_FIELDS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Field names to return. Omit for all non-binary fields (prefer listing only what you need).",
}
_CONTEXT = {
    "type": "object",
    "description": "Optional Odoo context, e.g. {\"lang\": \"vi_VN\", \"active_test\": false}",
}

READ_ANN = {"readOnlyHint": True, "openWorldHint": True}

TOOLS: list[dict] = [
    {
        "name": "odoo_server_info",
        "description": "Show the Odoo server URL, version, database and the authenticated user. Use first to verify the connection.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": READ_ANN,
    },
    {
        "name": "odoo_list_models",
        "description": "List installed Odoo models (technical name + label), optionally filtered by a substring of the name or label.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Substring to match, e.g. 'sale' or 'invoice'"},
                "limit": {"type": "integer", "default": 100},
            },
        },
        "annotations": READ_ANN,
    },
    {
        "name": "odoo_get_fields",
        "description": "Describe the fields of a model (label, type, required, readonly, relation, selection values). Use before building domains or writing values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": _MODEL,
                "fields": {"type": "array", "items": {"type": "string"}, "description": "Only describe these fields"},
                "query": {"type": "string", "description": "Only fields whose name or label contains this substring"},
            },
            "required": ["model"],
        },
        "annotations": READ_ANN,
    },
    {
        "name": "odoo_search_read",
        "description": "Search records of a model and return their field values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": _MODEL,
                "domain": _DOMAIN,
                "fields": _FIELDS,
                "limit": {"type": "integer", "default": DEFAULT_LIMIT, "description": f"Max records (<= {MAX_LIMIT})"},
                "offset": {"type": "integer", "default": 0},
                "order": {"type": "string", "description": "e.g. 'create_date desc, id'"},
                "context": _CONTEXT,
            },
            "required": ["model"],
        },
        "annotations": READ_ANN,
    },
    {
        "name": "odoo_read",
        "description": "Read specific records by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": _MODEL, "ids": _IDS, "fields": _FIELDS, "context": _CONTEXT},
            "required": ["model", "ids"],
        },
        "annotations": READ_ANN,
    },
    {
        "name": "odoo_search_count",
        "description": "Count records matching a domain.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": _MODEL, "domain": _DOMAIN, "context": _CONTEXT},
            "required": ["model"],
        },
        "annotations": READ_ANN,
    },
    {
        "name": "odoo_read_group",
        "description": "Aggregate records (like SQL GROUP BY), e.g. total sales per customer or invoices per month.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": _MODEL,
                "domain": _DOMAIN,
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Aggregates, e.g. [\"amount_total:sum\"]",
                },
                "groupby": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Group keys, e.g. [\"partner_id\"] or [\"date_order:month\"]",
                },
                "limit": {"type": "integer"},
                "orderby": {"type": "string"},
                "lazy": {"type": "boolean", "default": False},
                "context": _CONTEXT,
            },
            "required": ["model", "fields", "groupby"],
        },
        "annotations": READ_ANN,
    },
]

WRITE_TOOLS: list[dict] = [
    {
        "name": "odoo_create",
        "description": "Create one record. Returns the new ID. Confirm values with the user before creating business documents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": _MODEL,
                "values": {"type": "object", "description": "Field values, e.g. {\"name\": \"ACME\", \"email\": \"a@b.vn\"}"},
                "context": _CONTEXT,
            },
            "required": ["model", "values"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
    },
    {
        "name": "odoo_write",
        "description": "Update fields on existing records.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": _MODEL, "ids": _IDS, "values": {"type": "object"}, "context": _CONTEXT},
            "required": ["model", "ids", "values"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "odoo_unlink",
        "description": "Permanently delete records. Prefer archiving (write active=false) when the model supports it. Always confirm with the user first.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": _MODEL, "ids": _IDS, "context": _CONTEXT},
            "required": ["model", "ids"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True},
    },
    {
        "name": "odoo_call_method",
        "description": (
            "Call any public model method via execute_kw, e.g. sale.order action_confirm on [ids], "
            "account.move action_post, or a name_search. Methods starting with '_' are private and rejected by Odoo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": _MODEL,
                "method": {"type": "string"},
                "args": {"type": "array", "items": {}, "description": "Positional args; for record methods the first is the list of IDs"},
                "kwargs": {"type": "object"},
            },
            "required": ["model", "method"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True},
    },
]


def _kw_with_context(args: dict, **kwargs) -> dict:
    if args.get("context"):
        kwargs["context"] = args["context"]
    return kwargs


def _limit(value, default=DEFAULT_LIMIT) -> int:
    try:
        n = int(value if value is not None else default)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, MAX_LIMIT))


def _tool_server_info(c: OdooClient, a: dict):
    version = c.version()
    uid = c.login()
    user = c.execute("res.users", "read", [[uid]], {"fields": ["name", "login", "company_id", "lang", "tz"]})
    return {
        "url": c.url,
        "database": c.db,
        "server_version": version.get("server_version"),
        "user": user[0] if user else {"id": uid},
        "read_only": c.read_only,
    }


def _tool_list_models(c: OdooClient, a: dict):
    q = (a.get("query") or "").strip()
    domain = ["|", ["model", "ilike", q], ["name", "ilike", q]] if q else []
    return c.execute(
        "ir.model", "search_read", [domain],
        {"fields": ["model", "name"], "limit": _limit(a.get("limit"), 100), "order": "model"},
    )


def _tool_get_fields(c: OdooClient, a: dict):
    attrs = ["string", "type", "required", "readonly", "relation", "selection", "help"]
    meta = c.execute(a["model"], "fields_get", [a.get("fields") or []], {"attributes": attrs})
    q = (a.get("query") or "").lower()
    if q:
        meta = {k: v for k, v in meta.items() if q in k.lower() or q in str(v.get("string", "")).lower()}
    return meta


def _tool_search_read(c: OdooClient, a: dict):
    model = a["model"]
    kwargs = _kw_with_context(
        a,
        fields=a.get("fields") or c.default_fields(model),
        limit=_limit(a.get("limit")),
        offset=int(a.get("offset") or 0),
    )
    if a.get("order"):
        kwargs["order"] = a["order"]
    records = c.execute(model, "search_read", [a.get("domain") or []], kwargs)
    return {"count": len(records), "offset": kwargs["offset"], "records": records}


def _tool_read(c: OdooClient, a: dict):
    model = a["model"]
    fields = a.get("fields") or c.default_fields(model)
    return c.execute(model, "read", [a["ids"]], _kw_with_context(a, fields=fields))


def _tool_search_count(c: OdooClient, a: dict):
    return {"count": c.execute(a["model"], "search_count", [a.get("domain") or []], _kw_with_context(a))}


def _tool_read_group(c: OdooClient, a: dict):
    kwargs = _kw_with_context(a, lazy=bool(a.get("lazy", False)))
    if a.get("limit"):
        kwargs["limit"] = _limit(a["limit"])
    if a.get("orderby"):
        kwargs["orderby"] = a["orderby"]
    return c.execute(a["model"], "read_group", [a.get("domain") or [], a["fields"], a["groupby"]], kwargs)


def _tool_create(c: OdooClient, a: dict):
    new_id = c.execute(a["model"], "create", [a["values"]], _kw_with_context(a))
    return {"id": new_id}


def _tool_write(c: OdooClient, a: dict):
    return {"ok": c.execute(a["model"], "write", [a["ids"], a["values"]], _kw_with_context(a))}


def _tool_unlink(c: OdooClient, a: dict):
    return {"ok": c.execute(a["model"], "unlink", [a["ids"]], _kw_with_context(a))}


def _tool_call_method(c: OdooClient, a: dict):
    return {"result": c.execute(a["model"], a["method"], a.get("args") or [], a.get("kwargs") or {})}


HANDLERS = {
    "odoo_server_info": _tool_server_info,
    "odoo_list_models": _tool_list_models,
    "odoo_get_fields": _tool_get_fields,
    "odoo_search_read": _tool_search_read,
    "odoo_read": _tool_read,
    "odoo_search_count": _tool_search_count,
    "odoo_read_group": _tool_read_group,
    "odoo_create": _tool_create,
    "odoo_write": _tool_write,
    "odoo_unlink": _tool_unlink,
    "odoo_call_method": _tool_call_method,
}
WRITE_TOOL_NAMES = {t["name"] for t in WRITE_TOOLS}


def _text_result(payload, is_error: bool = False) -> dict:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=1, default=str)
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + (
            f"\n... [truncated {len(text) - MAX_OUTPUT_CHARS} chars; request fewer fields or a smaller limit]"
        )
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# ---------------------------------------------------------------------------
# MCP stdio loop
# ---------------------------------------------------------------------------


class McpServer:
    def __init__(self, client: OdooClient):
        self.client = client

    def tools(self) -> list[dict]:
        return TOOLS if self.client.read_only else TOOLS + WRITE_TOOLS

    def call_tool(self, name: str, args: dict) -> dict:
        if name not in HANDLERS or (self.client.read_only and name in WRITE_TOOL_NAMES):
            return _text_result(f"Unknown or disabled tool: {name}", is_error=True)
        try:
            return _text_result(HANDLERS[name](self.client, args or {}))
        except OdooError as exc:
            return _text_result(f"Odoo error: {exc}", is_error=True)
        except KeyError as exc:
            return _text_result(f"Missing required argument: {exc}", is_error=True)

    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method")
        msg_id = msg.get("id")
        if msg_id is None:  # notification (initialized, cancelled, ...)
            return None
        params = msg.get("params") or {}
        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            result = {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    f"Tools for the Odoo ERP at {self.client.url}. Inspect models with odoo_get_fields "
                    "before querying; always pass explicit `fields` and a small `limit`. Confirm with the "
                    "user before create/write/unlink/call_method."
                ),
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.tools()}
        elif method == "tools/call":
            result = self.call_tool(params.get("name", ""), params.get("arguments") or {})
        else:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def serve(self, stdin=sys.stdin, stdout=sys.stdout) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            else:
                try:
                    reply = self.handle(msg)
                except Exception as exc:  # keep the server alive; report to client and stderr
                    traceback.print_exc(file=sys.stderr)
                    reply = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": str(exc)}}
            if reply is not None:
                stdout.write(json.dumps(reply, ensure_ascii=False, default=str) + "\n")
                stdout.flush()


def main() -> None:
    McpServer(OdooClient()).serve()


if __name__ == "__main__":
    main()
