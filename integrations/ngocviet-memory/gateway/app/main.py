from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .logging_config import configure_logging
from .mem0_client import Mem0Client
from .routes import health, memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.mem0_client = Mem0Client(
        base_url=settings.mem0_api_url,
        api_key=settings.mem0_api_key,
        auth_header=settings.mem0_auth_header,
        auth_scheme=settings.mem0_auth_scheme,
        timeout_seconds=settings.mem0_request_timeout_seconds,
    )
    try:
        yield
    finally:
        await app.state.mem0_client.aclose()


app = FastAPI(
    title="NgocViet Memory Gateway",
    description="Sole access path from Hermes/OpenClaw to the shared Mem0 memory service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(memory.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Client-supplied agent_id/app_id (forbidden extra fields) surface here
    # as a 422 rather than being silently dropped — see schemas.py.
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
