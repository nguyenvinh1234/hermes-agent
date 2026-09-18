"""Minimal in-memory per-client rate limiter (fixed 60s window).

Single-instance only by design (v1 scope, section 35 of the rollout spec).
If the gateway is ever horizontally scaled, replace this with a shared
store (e.g. Redis) — documented as a known limitation in docs/security.md.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, client_id: str, limit_per_minute: int) -> None:
        now = time.monotonic()
        window_start = now - 60.0
        hits = self._hits[client_id]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded.",
            )
        hits.append(now)


rate_limiter = RateLimiter()
