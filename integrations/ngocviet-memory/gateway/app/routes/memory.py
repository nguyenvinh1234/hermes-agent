from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import policy
from ..auth import get_client_identity
from ..config import ClientIdentity, Settings, get_settings
from ..logging_config import audit_log
from ..mem0_client import Mem0Client, Mem0Error
from ..ratelimit import rate_limiter
from ..sensitive_data import detect_secret
from ..schemas import (
    MemoryAddRequest,
    MemoryAddResponse,
    MemoryRecord,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResultItem,
    MemoryUpdateRequest,
    MessageResponse,
)

router = APIRouter(prefix="/v1/memory", tags=["memory"])


def _get_mem0(request: Request) -> Mem0Client:
    return request.app.state.mem0_client


def _enforce_rate_limit(identity: ClientIdentity) -> None:
    rate_limiter.check(identity.client_id, identity.rate_limit_per_minute)


@router.post("/add", response_model=MemoryAddResponse, status_code=status.HTTP_201_CREATED)
async def add_memory(
    req: MemoryAddRequest,
    request: Request,
    identity: ClientIdentity = Depends(get_client_identity),
    settings: Settings = Depends(get_settings),
) -> MemoryAddResponse:
    _enforce_rate_limit(identity)
    start = time.monotonic()

    secret_match = detect_secret(req.content)
    if secret_match is not None:
        audit_log(
            client_id=identity.client_id,
            operation="add",
            status="rejected",
            user_id=req.user_id,
            project_id=req.project_id,
            latency_ms=(time.monotonic() - start) * 1000,
            extra={"reason": "REDACTED_SECRET", "pattern": secret_match.pattern_name},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content appears to contain a secret/credential and was not stored.",
        )

    metadata = policy.build_write_metadata(identity, req, settings)
    mem0 = _get_mem0(request)
    try:
        result = await mem0.add_memory(
            content=req.content, user_id=req.user_id, agent_id=identity.agent_id, metadata=metadata
        )
    except Mem0Error as exc:
        audit_log(
            client_id=identity.client_id,
            operation="add",
            status="error",
            user_id=req.user_id,
            project_id=req.project_id,
            latency_ms=(time.monotonic() - start) * 1000,
            error=str(exc.status_code),
        )
        raise HTTPException(status_code=502 if exc.status_code >= 500 else exc.status_code, detail="Upstream memory store error.")

    memory_id = _extract_first_id(result)
    audit_log(
        client_id=identity.client_id,
        operation="add",
        status="success",
        user_id=req.user_id,
        project_id=req.project_id,
        latency_ms=(time.monotonic() - start) * 1000,
    )
    return MemoryAddResponse(id=memory_id)


def _extract_first_id(mem0_result: object) -> str:
    if isinstance(mem0_result, dict):
        results = mem0_result.get("results") or mem0_result.get("memories")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict) and "id" in first:
                return str(first["id"])
        if "id" in mem0_result:
            return str(mem0_result["id"])
    if isinstance(mem0_result, list) and mem0_result and isinstance(mem0_result[0], dict):
        return str(mem0_result[0].get("id", ""))
    return ""


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    req: MemorySearchRequest,
    request: Request,
    identity: ClientIdentity = Depends(get_client_identity),
    settings: Settings = Depends(get_settings),
) -> MemorySearchResponse:
    _enforce_rate_limit(identity)
    start = time.monotonic()
    mem0 = _get_mem0(request)

    overfetch = min(req.limit * settings.search_overfetch_multiplier, 200)
    try:
        raw_results = await mem0.search(query=req.query, user_id=req.user_id, top_k=overfetch)
    except Mem0Error as exc:
        audit_log(
            client_id=identity.client_id,
            operation="search",
            status="error",
            user_id=req.user_id,
            project_id=req.project_id,
            latency_ms=(time.monotonic() - start) * 1000,
            error=str(exc.status_code),
        )
        raise HTTPException(status_code=502 if exc.status_code >= 500 else exc.status_code, detail="Upstream memory store error.")

    filtered = policy.filter_search_results(
        identity,
        raw_results,
        requested_classes=req.memory_class,
        requested_project_id=req.project_id,
        limit=req.limit,
    )
    audit_log(
        client_id=identity.client_id,
        operation="search",
        status="success",
        user_id=req.user_id,
        project_id=req.project_id,
        latency_ms=(time.monotonic() - start) * 1000,
        extra={"result_count": len(filtered)},
    )
    return MemorySearchResponse(
        results=[
            MemorySearchResultItem(
                id=str(r.get("id", "")),
                memory=str(r.get("memory", r.get("text", ""))),
                score=float(r.get("score", 0.0)),
                metadata=r.get("metadata") or {},
            )
            for r in filtered
        ]
    )


@router.get("/{memory_id}", response_model=MemoryRecord)
async def get_memory(
    memory_id: str,
    request: Request,
    identity: ClientIdentity = Depends(get_client_identity),
) -> MemoryRecord:
    _enforce_rate_limit(identity)
    mem0 = _get_mem0(request)
    try:
        record = await mem0.get_memory(memory_id)
    except Mem0Error as exc:
        raise HTTPException(status_code=404 if exc.status_code == 404 else 502, detail="Memory not found or upstream error.")

    metadata = record.get("metadata") or {}
    if not policy.is_visible(
        identity,
        metadata,
        requested_classes=list(policy.MemoryClass),
        requested_project_id=metadata.get("project_id"),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")

    return MemoryRecord(
        id=str(record.get("id", memory_id)),
        memory=str(record.get("memory", record.get("text", ""))),
        metadata=metadata,
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


@router.patch("/{memory_id}", response_model=MessageResponse)
async def update_memory(
    memory_id: str,
    req: MemoryUpdateRequest,
    request: Request,
    identity: ClientIdentity = Depends(get_client_identity),
) -> MessageResponse:
    _enforce_rate_limit(identity)
    mem0 = _get_mem0(request)

    if req.content is not None:
        secret_match = detect_secret(req.content)
        if secret_match is not None:
            audit_log(
                client_id=identity.client_id,
                operation="update",
                status="rejected",
                extra={"reason": "REDACTED_SECRET", "pattern": secret_match.pattern_name},
            )
            raise HTTPException(status_code=400, detail="Content appears to contain a secret/credential and was not stored.")

    try:
        existing = await mem0.get_memory(memory_id)
    except Mem0Error:
        raise HTTPException(status_code=404, detail="Memory not found.")

    existing_metadata = existing.get("metadata") or {}
    if existing_metadata.get("agent_id") != identity.agent_id and existing_metadata.get(
        "memory_class"
    ) not in ("shared",):
        # Only the owning agent may edit agent_private/project/temporary
        # memories it did not create; shared memories may be updated by any
        # authenticated client (e.g. to mark superseded).
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to update this memory.")

    metadata_patch = dict(existing_metadata)
    if req.status is not None:
        metadata_patch["status"] = req.status.value
    if req.sensitivity is not None:
        metadata_patch["sensitivity"] = req.sensitivity
    metadata_patch["updated_by"] = identity.client_id

    try:
        await mem0.update_memory(memory_id, text=req.content, metadata=metadata_patch)
    except Mem0Error as exc:
        raise HTTPException(status_code=502 if exc.status_code >= 500 else exc.status_code, detail="Upstream memory store error.")

    audit_log(client_id=identity.client_id, operation="update", status="success")
    return MessageResponse(status="updated")


@router.delete("/{memory_id}", response_model=MessageResponse)
async def delete_memory(
    memory_id: str,
    request: Request,
    identity: ClientIdentity = Depends(get_client_identity),
) -> MessageResponse:
    _enforce_rate_limit(identity)
    mem0 = _get_mem0(request)

    try:
        existing = await mem0.get_memory(memory_id)
    except Mem0Error:
        raise HTTPException(status_code=404, detail="Memory not found.")

    existing_metadata = existing.get("metadata") or {}
    if existing_metadata.get("agent_id") != identity.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to delete this memory.")

    try:
        await mem0.delete_memory(memory_id)
    except Mem0Error as exc:
        raise HTTPException(status_code=502 if exc.status_code >= 500 else exc.status_code, detail="Upstream memory store error.")

    audit_log(client_id=identity.client_id, operation="delete", status="success")
    return MessageResponse(status="deleted")
