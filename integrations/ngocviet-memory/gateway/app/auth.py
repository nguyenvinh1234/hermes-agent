"""Per-client API key authentication.

Each client (Hermes, OpenClaw, ...) gets its own key via
`X-NgocViet-API-Key`. Keys map 1:1 to a fixed client_id/agent_id — clients
never choose their own identity (see config.Settings.client_registry).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from .config import ClientIdentity, Settings, get_settings

API_KEY_HEADER = "X-NgocViet-API-Key"


async def get_client_identity(
    request: Request, settings: Settings = Depends(get_settings)
) -> ClientIdentity:
    api_key = request.headers.get(API_KEY_HEADER)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {API_KEY_HEADER} header.",
        )
    identity = settings.client_registry.get(api_key)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return identity
