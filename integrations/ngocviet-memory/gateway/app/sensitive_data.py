"""Sensitive-data filter (section 13).

Applied to every `content` string before it is ever sent to Mem0. On a hit,
the write is rejected (fail closed) — we never store a redacted-but-partial
copy of a secret. Callers see a generic 400; audit logs record the pattern
name only (never the matched text).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_PATTERNS: dict[str, re.Pattern[str]] = {
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9\-_.=]{10,}\b", re.IGNORECASE),
    "github_pat": re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "generic_api_key_assignment": re.compile(
        r"\b(api[_-]?key|access[_-]?token|secret|password|passwd)\s*[:=]\s*\S{6,}",
        re.IGNORECASE,
    ),
    "basic_auth_url": re.compile(r"://[^\s:@/]+:[^\s:@/]+@"),
}


@dataclass(frozen=True)
class SensitiveDataMatch:
    pattern_name: str


def detect_secret(text: str) -> Optional[SensitiveDataMatch]:
    for name, pattern in _PATTERNS.items():
        if pattern.search(text):
            return SensitiveDataMatch(pattern_name=name)
    return None
