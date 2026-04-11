from __future__ import annotations

import secrets
from typing import Any, Dict

try:
    from flask import g, request
except Exception:  # pragma: no cover
    g = None
    request = None


def ensure_request_id() -> str:
    """
    Ensure every request has a correlation id.
    Reuses X-Request-ID when present; otherwise creates a short id.
    """
    rid = ""
    if request is not None:
        rid = (request.headers.get("X-Request-ID") or "").strip()
    if not rid:
        rid = secrets.token_hex(8)
    if g is not None:
        try:
            g.request_id = rid
        except Exception:
            pass
    return rid


def request_id() -> str:
    if g is not None:
        rid = getattr(g, "request_id", "") or ""
        if rid:
            return rid
    return ensure_request_id()


def incident_code(family: str) -> str:
    fam = (family or "REL-GEN").strip().upper()
    return f"{fam}-{secrets.token_hex(3).upper()}"


def emit_event(logger, event: str, **fields: Any) -> None:
    payload: Dict[str, Any] = {"event": event, "request_id": request_id(), **fields}
    kv = " ".join(f"{k}={payload[k]!r}" for k in sorted(payload.keys()))
    logger.info("[reliability] %s", kv)


def safe_user_error(message: str, code: str) -> str:
    return f"{message} (incident: {code})"
