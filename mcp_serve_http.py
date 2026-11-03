"""Streamable-HTTP transport for ``hermes mcp serve --http``.

Lets remote MCP clients reach Hermes: ChatGPT (developer-mode connectors) and Claude
(custom connectors, synced to the mobile apps) can only talk to an HTTPS URL, never a
stdio process. Both accept a connector with no OAuth, so the gate is a capability URL:
``/mcp/<token>``. Clients that can send headers may instead use ``/mcp`` with
``Authorization: Bearer <token>``. Everything else is 404, including the OAuth discovery
probes, which tells the client "no OAuth here".

The token is a secret, so it lives in ``.env`` (``MCP_SERVE_TOKEN``), generated on first
run. Host/port are plain CLI flags. Access logging is off: the request path carries the token.
"""

from __future__ import annotations

import hmac
import json
import secrets
import sys
from typing import Optional

TOKEN_ENV = "MCP_SERVE_TOKEN"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
_INNER_PATH = "/mcp"


def resolve_token(rotate: bool = False) -> str:
    """The persisted serve token, generating (or with ``rotate``, replacing) it in ``.env``."""
    from hermes_cli.config import get_env_value, save_env_value

    token = None if rotate else (get_env_value(TOKEN_ENV) or "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        save_env_value(TOKEN_ENV, token)
    return token


def _bearer(scope) -> str:
    for name, value in scope.get("headers") or ():
        if name.lower() == b"authorization":
            scheme, _, cred = value.decode("latin-1").partition(" ")
            return cred.strip() if scheme.lower() == "bearer" else ""
    return ""


class TokenGate:
    """ASGI wrapper admitting only ``/mcp/<token>`` or ``/mcp`` + bearer token."""

    def __init__(self, app, token: str):
        if not token:
            raise ValueError("TokenGate requires a non-empty token")
        self.app = app
        self._token = token.encode()

    def _authorized_path(self, scope) -> bool:
        path = (scope.get("path") or "").rstrip("/")
        if path == _INNER_PATH:
            return hmac.compare_digest(_bearer(scope).encode(), self._token)
        prefix = _INNER_PATH + "/"
        return path.startswith(prefix) and hmac.compare_digest(path[len(prefix):].encode(), self._token)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":  # lifespan: the inner app starts its session manager here
            return await self.app(scope, receive, send)
        if not self._authorized_path(scope):
            body = json.dumps({"error": "not found"}).encode()
            await send({"type": "http.response.start", "status": 404,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        inner = dict(scope, path=_INNER_PATH, raw_path=_INNER_PATH.encode())
        return await self.app(inner, receive, send)


def build_http_app(server, token: str):
    """The gated ASGI app for an ``MCPServer``.

    Stateless: phones drop connections and tunnels recycle them, so no request may depend
    on a server-side session surviving. DNS-rebinding protection is off because the Host
    header is whatever tunnel the user puts in front (Cloudflare, Tailscale Funnel, ngrok);
    the token, not the Host header, is the access control.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    inner = server.streamable_http_app(
        streamable_http_path=_INNER_PATH, stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    return TokenGate(inner, token)


def print_connect_help(host: str, port: int, token: str, public_url: Optional[str]) -> None:
    local = f"http://{host}:{port}{_INNER_PATH}/{token}"
    lines = [
        "Hermes MCP server (streamable HTTP) is running.",
        f"  Local URL:  {local}",
    ]
    if public_url:
        lines.append(f"  Connector URL (paste into ChatGPT / Claude):  {public_url.rstrip('/')}{_INNER_PATH}/{token}")
    else:
        lines += [
            "",
            "To use it from ChatGPT or Claude (web + phone apps) expose it over HTTPS, e.g.:",
            f"  cloudflared tunnel --url http://{host}:{port}",
            f"  tailscale funnel {port}",
            f"then add a connector with URL  https://<public-host>{_INNER_PATH}/{token}  and no authentication.",
        ]
    lines += [
        "",
        "Keep this URL private: it grants control of this Hermes. Rotate with --rotate-token.",
        "Tasks are run by the kanban dispatcher inside the gateway: keep `hermes gateway` running.",
    ]
    print("\n".join(lines), file=sys.stderr, flush=True)


async def serve_http(server, *, host: str, port: int, token: str) -> None:
    import uvicorn

    config = uvicorn.Config(build_http_app(server, token), host=host, port=port,
                            access_log=False, log_level="warning", lifespan="on")
    await uvicorn.Server(config).serve()
