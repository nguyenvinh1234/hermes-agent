"""Thin async client for the self-hosted Mem0 REST API.

Targets the routes shipped by the mem0ai/mem0 `server/` FastAPI app
(POST /memories, POST /search, GET/PUT/DELETE /memories/{id}). Mem0 has no
dedicated health endpoint, so readiness is approximated by an authenticated
`GET /memories` probe with `top_k=1` (see `ping`/`probe_db`).

IMPORTANT: the exact auth header and a couple of field names can shift
between Mem0 releases. Pin the image tag in docker-compose.yml and verify
this client against that exact version's `/docs` (OpenAPI) during Phase 1
of the deployment runbook before going further — see docs/deployment.md.

The Mem0 admin/master API key lives ONLY here, inside the gateway process.
It is never echoed back to a caller and never logged.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class Mem0Error(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class Mem0Client:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        timeout_seconds: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {
            auth_header: (f"{auth_scheme} {api_key}" if auth_scheme else api_key),
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, retry_on_transport_error: bool = True, **kwargs: Any) -> httpx.Response:
        attempts = 2 if retry_on_transport_error else 1
        last_exc: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                return await self._client.request(method, path, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    break
        assert last_exc is not None
        raise Mem0Error(504, f"Mem0 unreachable: {last_exc}") from last_exc

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise Mem0Error(resp.status_code, resp.text[:500])

    async def ping(self) -> bool:
        try:
            resp = await self._request("GET", "/", retry_on_transport_error=False)
        except Mem0Error:
            return False
        # `/` redirects to /docs on a healthy instance; any non-5xx means the
        # process is up and accepting connections.
        return resp.status_code < 500

    async def probe_db(self, probe_user_id: str = "__ngocviet_health_probe__") -> bool:
        try:
            resp = await self._request(
                "GET",
                "/memories",
                params={"user_id": probe_user_id, "top_k": 1},
                retry_on_transport_error=False,
            )
        except Mem0Error:
            return False
        return resp.status_code < 500

    async def add_memory(
        self,
        *,
        content: str,
        user_id: str,
        agent_id: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "messages": [{"role": "user", "content": content}],
            "user_id": user_id,
            "agent_id": agent_id,
            "metadata": metadata,
        }
        resp = await self._request("POST", "/memories", json=payload)
        self._raise_for_status(resp)
        return resp.json()

    async def search(
        self,
        *,
        query: str,
        user_id: str,
        top_k: int,
        agent_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {"query": query, "user_id": user_id, "top_k": top_k}
        if agent_id:
            payload["agent_id"] = agent_id
        if filters:
            payload["filters"] = filters
        resp = await self._request("POST", "/search", json=payload)
        self._raise_for_status(resp)
        data = resp.json()
        return data.get("results", data) if isinstance(data, dict) else data

    async def get_memory(self, memory_id: str) -> Dict[str, Any]:
        resp = await self._request("GET", f"/memories/{memory_id}")
        self._raise_for_status(resp)
        return resp.json()

    async def update_memory(
        self, memory_id: str, *, text: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if text is not None:
            payload["text"] = text
        if metadata is not None:
            payload["metadata"] = metadata
        resp = await self._request("PUT", f"/memories/{memory_id}", json=payload)
        self._raise_for_status(resp)
        return resp.json()

    async def delete_memory(self, memory_id: str) -> None:
        resp = await self._request("DELETE", f"/memories/{memory_id}")
        self._raise_for_status(resp)
