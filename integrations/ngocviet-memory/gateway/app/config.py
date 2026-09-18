"""Gateway configuration.

All values come from environment variables (loaded from `.env` by the process
supervisor / docker-compose `env_file`, never hardcoded). See
`.env.example` at the repo root of this subproject for the full list of
placeholders and `docs/security.md` for what must never be committed.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, NamedTuple

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientIdentity(NamedTuple):
    """Resolved identity for an authenticated caller.

    `agent_id` / `app_id` here are the ONLY source of truth for those fields
    on every write — a client can never set them itself (see schemas.py,
    which uses extra="forbid" to hard-reject any attempt).
    """

    client_id: str
    agent_id: str
    app_id: str
    rate_limit_per_minute: int


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Mem0 upstream (admin/master credentials — NEVER forwarded to clients) ---
    mem0_api_url: str = Field(..., alias="MEM0_API_URL")
    mem0_api_key: str = Field(..., alias="MEM0_API_KEY")
    # Self-hosted Mem0 server auth varies by pinned version/build. Confirm the
    # exact header against the OpenAPI docs of the pinned image during
    # deployment (docs/deployment.md Phase 1) and adjust here if needed.
    mem0_auth_header: str = Field(default="Authorization", alias="MEM0_AUTH_HEADER")
    mem0_auth_scheme: str = Field(default="Bearer", alias="MEM0_AUTH_SCHEME")
    mem0_request_timeout_seconds: float = Field(default=8.0, alias="MEM0_REQUEST_TIMEOUT_SECONDS")

    # --- Gateway clients. This is the stable extension point for future
    # callers (OpenClaw, n8n, DeepSeek Harness, Codex, ...) — adding one is
    # a `.env` change only, never a code change. List the client ids here,
    # then set MEMORY_GATEWAY_API_KEY_<ID> (required) and optionally
    # RATE_LIMIT_PER_MINUTE_<ID> for each one. See client_registry below. ---
    memory_gateway_client_ids: str = Field(default="hermes,openclaw", alias="MEMORY_GATEWAY_CLIENT_IDS")
    default_rate_limit_per_minute: int = Field(default=60, alias="DEFAULT_RATE_LIMIT_PER_MINUTE")

    # --- Namespace defaults ---
    app_id: str = Field(default="ngocviet-ai-business-os", alias="NGOCVIET_APP_ID")

    # --- Memory policy ---
    temporary_default_ttl_seconds: int = Field(default=604800, alias="TEMPORARY_DEFAULT_TTL_SECONDS")
    search_overfetch_multiplier: int = Field(default=3, alias="SEARCH_OVERFETCH_MULTIPLIER")

    # --- Bind address. Port defaults to 8077 deliberately — NOT one of the
    # ports the deployment runbook flags as commonly-occupied
    # (3000/3080/5432/8000/8080/8090/8888/9000). Confirm free during the real
    # Phase 0 audit on the target server and override here if it collides. ---
    gateway_bind_host: str = Field(default="127.0.0.1", alias="GATEWAY_BIND_HOST")
    gateway_bind_port: int = Field(default=8077, alias="GATEWAY_BIND_PORT")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("mem0_api_url")
    @classmethod
    def _no_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def client_registry(self) -> Dict[str, ClientIdentity]:
        """Map API key -> resolved identity.

        Extend by adding the client id to MEMORY_GATEWAY_CLIENT_IDS and
        setting MEMORY_GATEWAY_API_KEY_<ID> (+ optionally
        RATE_LIMIT_PER_MINUTE_<ID>) in `.env` — no code change needed. This
        is what lets Hermes, OpenClaw, and future callers (n8n, DeepSeek
        Harness, Codex, ...) all authenticate against the same stable API
        contract (docs/api-contract.md). A client never chooses its own
        client_id/agent_id — this registry is the only source of truth.
        """
        registry: Dict[str, ClientIdentity] = {}
        client_ids = [c.strip() for c in self.memory_gateway_client_ids.split(",") if c.strip()]
        for client_id in client_ids:
            env_suffix = client_id.upper().replace("-", "_")
            api_key = os.environ.get(f"MEMORY_GATEWAY_API_KEY_{env_suffix}", "")
            if not api_key:
                continue
            rate_limit_raw = os.environ.get(f"RATE_LIMIT_PER_MINUTE_{env_suffix}")
            rate_limit = int(rate_limit_raw) if rate_limit_raw else self.default_rate_limit_per_minute
            registry[api_key] = ClientIdentity(
                client_id=client_id,
                agent_id=client_id,
                app_id=self.app_id,
                rate_limit_per_minute=rate_limit,
            )
        return registry


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
