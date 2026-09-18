"""Request/response contracts for the NgocViet Memory Gateway.

Every request model uses `extra="forbid"`: if a client sends `agent_id`,
`app_id`, or `created_by` in the body, the request is rejected with 422
rather than silently ignored — the gateway is the only place those fields
are ever set (see policy.py).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryClass(str, Enum):
    SHARED = "shared"
    AGENT_PRIVATE = "agent_private"
    PROJECT = "project"
    TEMPORARY = "temporary"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class MemoryAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1, max_length=8000)
    memory_class: MemoryClass = MemoryClass.AGENT_PRIVATE
    project_id: str = Field(default="global", min_length=1, max_length=128)
    domain: str = Field(default="general", min_length=1, max_length=128)
    sensitivity: str = Field(default="internal", max_length=32)
    supersedes: Optional[str] = Field(default=None, max_length=128)
    ttl_seconds: Optional[int] = Field(default=None, ge=60, le=31536000)


class MemoryAddResponse(BaseModel):
    id: str
    status: str = "created"


class MemorySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=50)
    memory_class: List[MemoryClass] = Field(
        default_factory=lambda: [MemoryClass.SHARED, MemoryClass.AGENT_PRIVATE]
    )
    project_id: Optional[str] = Field(default=None, max_length=128)
    domain: Optional[str] = Field(default=None, max_length=128)


class MemorySearchResultItem(BaseModel):
    id: str
    memory: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySearchResponse(BaseModel):
    results: List[MemorySearchResultItem]


class MemoryRecord(BaseModel):
    id: str
    memory: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: Optional[str] = Field(default=None, min_length=1, max_length=8000)
    status: Optional[MemoryStatus] = None
    sensitivity: Optional[str] = Field(default=None, max_length=32)


class MessageResponse(BaseModel):
    status: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    ready: bool
    components: Dict[str, bool]
