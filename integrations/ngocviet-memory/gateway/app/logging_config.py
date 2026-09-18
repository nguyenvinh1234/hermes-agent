"""Structured JSON audit logging (section 14).

Logs go to stdout only — the docker-compose service sets the `json-file`
log driver with `max-size`/`max-file` for rotation (section 14 "Log
rotate"), so the app never needs to manage log files itself.

Never pass API keys, passwords, or raw sensitive memory content into these
fields. `content_preview` is intentionally not logged for `add` operations;
only length and whether a secret was rejected.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Optional

_AUDIT_LOGGER_NAME = "ngocviet.memory.audit"


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.handlers = [handler]

    audit_logger = logging.getLogger(_AUDIT_LOGGER_NAME)
    audit_logger.setLevel(level)
    audit_logger.propagate = True


def audit_log(
    *,
    client_id: str,
    operation: str,
    status: str,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    error: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    record: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "client_id": client_id,
        "operation": operation,
        "status": status,
    }
    if user_id is not None:
        record["user_id"] = user_id
    if project_id is not None:
        record["project_id"] = project_id
    if latency_ms is not None:
        record["latency_ms"] = round(latency_ms, 2)
    if error is not None:
        record["error"] = error
    if extra:
        record.update(extra)
    logging.getLogger(_AUDIT_LOGGER_NAME).info(json.dumps(record, ensure_ascii=False))
