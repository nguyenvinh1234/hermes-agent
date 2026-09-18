from __future__ import annotations

import os

os.environ.setdefault("MEM0_API_URL", "http://mem0.internal:8000")
os.environ.setdefault("MEM0_API_KEY", "test-mem0-admin-key")
os.environ.setdefault("MEMORY_GATEWAY_API_KEY_HERMES", "test-hermes-key")
os.environ.setdefault("MEMORY_GATEWAY_API_KEY_OPENCLAW", "test-openclaw-key")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE_HERMES", "1000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE_OPENCLAW", "1000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.mem0_client import Mem0Error  # noqa: E402
from app.ratelimit import rate_limiter  # noqa: E402

HERMES_HEADERS = {"X-NgocViet-API-Key": "test-hermes-key"}
OPENCLAW_HEADERS = {"X-NgocViet-API-Key": "test-openclaw-key"}


class FakeMem0Client:
    """In-memory stand-in for the real Mem0 REST API, used by route tests
    so they exercise gateway policy/auth logic without a live Mem0/Postgres.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._next_id = 1

    async def aclose(self) -> None:
        pass

    async def ping(self) -> bool:
        return True

    async def probe_db(self, probe_user_id: str = "x") -> bool:
        return True

    async def add_memory(self, *, content, user_id, agent_id, metadata):
        memory_id = str(self._next_id)
        self._next_id += 1
        record = {"id": memory_id, "memory": content, "metadata": dict(metadata), "user_id": user_id}
        self._store[memory_id] = record
        return {"results": [{"id": memory_id}]}

    async def search(self, *, query, user_id, top_k, agent_id=None, filters=None):
        results = []
        query_words = set(query.lower().split())
        for r in self._store.values():
            if r["user_id"] != user_id:
                continue
            memory_words = set(r["memory"].lower().replace(":", "").split())
            if query_words & memory_words:
                results.append({**r, "score": 0.9})
        return results[:top_k]

    async def get_memory(self, memory_id):
        if memory_id not in self._store:
            raise Mem0Error(404, "not found")
        return self._store[memory_id]

    async def update_memory(self, memory_id, *, text=None, metadata=None):
        if memory_id not in self._store:
            raise Mem0Error(404, "not found")
        record = self._store[memory_id]
        if text is not None:
            record["memory"] = text
        if metadata is not None:
            record["metadata"] = metadata
        return record

    async def delete_memory(self, memory_id):
        if memory_id not in self._store:
            raise Mem0Error(404, "not found")
        del self._store[memory_id]


@pytest.fixture
def client():
    rate_limiter._hits.clear()
    with TestClient(app) as c:
        c.app.state.mem0_client = FakeMem0Client()
        yield c
