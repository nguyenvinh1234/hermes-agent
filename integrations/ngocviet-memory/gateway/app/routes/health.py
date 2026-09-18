from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..mem0_client import Mem0Client
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    mem0: Mem0Client = request.app.state.mem0_client
    mem0_ok = await mem0.ping()
    postgres_ok = await mem0.probe_db() if mem0_ok else False
    is_ready = mem0_ok and postgres_ok
    body = {
        "ready": is_ready,
        "components": {"gateway": True, "mem0": mem0_ok, "postgres": postgres_ok},
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=body)
