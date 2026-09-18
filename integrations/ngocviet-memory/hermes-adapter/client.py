"""HTTP client for the NgocViet Memory Gateway, used by the Hermes plugin.

Design goal: memory being unavailable must NEVER crash or hard-fail a
Hermes conversation turn (rollout spec section 32/33). Every public
function here catches its own errors, logs a warning, and returns a safe
"nothing happened" value instead of raising.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("hermes.plugins.memory_gateway")

DEFAULT_TIMEOUT_SECONDS = 5.0


def _base_url() -> Optional[str]:
    url = os.getenv("MEMORY_GATEWAY_URL")
    return url.rstrip("/") if url else None


def _api_key() -> Optional[str]:
    return os.getenv("MEMORY_GATEWAY_API_KEY")


def _headers() -> Dict[str, str]:
    return {"X-NgocViet-API-Key": _api_key() or "", "Content-Type": "application/json"}


def _available() -> bool:
    if not _base_url() or not _api_key():
        logger.warning("memory_gateway plugin: MEMORY_GATEWAY_URL/MEMORY_GATEWAY_API_KEY not set, skipping.")
        return False
    return True


def search(
    query: str,
    *,
    user_id: str,
    limit: int = 8,
    memory_class: Optional[List[str]] = None,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not _available():
        return []
    payload: Dict[str, Any] = {"user_id": user_id, "query": query, "limit": min(limit, 10)}
    if memory_class:
        payload["memory_class"] = memory_class
    if project_id:
        payload["project_id"] = project_id
    try:
        resp = requests.post(
            f"{_base_url()}/v1/memory/search",
            json=payload,
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.RequestException as exc:
        logger.warning("memory_search failed, degrading to no memory context: %s", exc)
        return []


def add(
    content: str,
    *,
    user_id: str,
    memory_class: str = "agent_private",
    project_id: str = "global",
    domain: str = "general",
) -> Optional[Dict[str, Any]]:
    if not _available():
        return None
    payload = {
        "user_id": user_id,
        "content": content,
        "memory_class": memory_class,
        "project_id": project_id,
        "domain": domain,
    }
    try:
        resp = requests.post(
            f"{_base_url()}/v1/memory/add",
            json=payload,
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        if resp.status_code == 400:
            # Sensitive-data filter rejected it — expected sometimes, not an error.
            logger.info("memory_add rejected by sensitive-data filter, not stored.")
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("memory_add failed, continuing without storing: %s", exc)
        return None


def feedback(memory_id: str, feedback_type: str, note: Optional[str] = None) -> bool:
    if not _available():
        return False
    if feedback_type not in ("confirmed", "outdated", "contradicted"):
        logger.warning("memory_feedback: unknown feedback_type %r, ignoring.", feedback_type)
        return False
    payload: Dict[str, Any] = {}
    if feedback_type in ("outdated", "contradicted"):
        payload["status"] = "superseded"
    try:
        resp = requests.patch(
            f"{_base_url()}/v1/memory/{memory_id}",
            json=payload,
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("memory_feedback failed for %s: %s", memory_id, exc)
        return False
