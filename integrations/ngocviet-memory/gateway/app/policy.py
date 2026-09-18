"""Namespace + memory-class policy enforcement (sections 9-12, 20, 26).

This is the ONLY place that decides:
  - what metadata a write is stamped with (client input is never trusted
    for agent_id/app_id/created_by — schemas.py already forbids sending
    them, this module supplies them),
  - whether a given stored memory is visible to a given caller.

Server-side, defense in depth: even though we also forward `filters` to
Mem0's own /search, we re-check every returned record here before it goes
back to a client, so a Mem0 filter bug/version mismatch never leaks data
across agents or projects.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .config import ClientIdentity, Settings
from .schemas import MemoryAddRequest, MemoryClass


def build_write_metadata(
    identity: ClientIdentity, req: MemoryAddRequest, settings: Settings
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "agent_id": identity.agent_id,
        "app_id": identity.app_id,
        "created_by": identity.client_id,
        "memory_class": req.memory_class.value,
        "project_id": req.project_id,
        "domain": req.domain,
        "sensitivity": req.sensitivity,
        "status": "active",
        "created_at": time.time(),
    }
    if req.supersedes:
        metadata["supersedes"] = req.supersedes
    if req.memory_class == MemoryClass.TEMPORARY:
        ttl = req.ttl_seconds or settings.temporary_default_ttl_seconds
        metadata["expires_at"] = time.time() + ttl
    return metadata


def is_visible(
    identity: ClientIdentity,
    record_metadata: Dict[str, Any],
    *,
    requested_classes: List[MemoryClass],
    requested_project_id: Optional[str],
) -> bool:
    """Server-side visibility check applied to every candidate search hit."""
    status = record_metadata.get("status", "active")
    if status in ("archived", "superseded"):
        return False

    raw_class = record_metadata.get("memory_class", MemoryClass.AGENT_PRIVATE.value)
    try:
        record_class = MemoryClass(raw_class)
    except ValueError:
        return False
    if record_class not in requested_classes:
        return False

    expires_at = record_metadata.get("expires_at")
    if expires_at is not None and time.time() > float(expires_at):
        return False

    if record_class == MemoryClass.AGENT_PRIVATE:
        return record_metadata.get("agent_id") == identity.agent_id

    if record_class == MemoryClass.PROJECT:
        if not requested_project_id:
            return False
        return record_metadata.get("project_id") == requested_project_id

    if record_class == MemoryClass.TEMPORARY:
        # Conservative default: temporary memories are only visible to the
        # agent that created them, same as agent_private, until a shared
        # temporary use case is actually needed.
        return record_metadata.get("agent_id") == identity.agent_id

    # SHARED
    return True


def filter_search_results(
    identity: ClientIdentity,
    raw_results: List[Dict[str, Any]],
    *,
    requested_classes: List[MemoryClass],
    requested_project_id: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    visible = [
        r
        for r in raw_results
        if is_visible(
            identity,
            r.get("metadata") or {},
            requested_classes=requested_classes,
            requested_project_id=requested_project_id,
        )
    ]
    return visible[:limit]
