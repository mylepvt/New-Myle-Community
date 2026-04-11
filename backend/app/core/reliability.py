"""
Reliability helpers — correlation ids, incident codes, structured ops logs.

Ported from Myle-Dashboard ``reliability.py`` (Flask ``g``/``request`` → Starlette
``Request.state`` + headers). ``RequestIdMiddleware`` normally sets
``request.state.request_id``; ``ensure_request_id`` fills it when missing (e.g. tests).
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from starlette.requests import Request

# Align with ``app.middleware.request_id`` inbound cap.
_MAX_HEADER_RID_LEN = 128


def ensure_request_id(request: Request) -> str:
    """
    Return a correlation id for this request: prefer ``state.request_id``, else
    inbound ``X-Request-ID``, else a new hex id (and assign ``state.request_id``).
    """
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    raw = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
    if raw and len(raw) <= _MAX_HEADER_RID_LEN:
        rid = raw.strip()
    else:
        rid = secrets.token_hex(8)
    request.state.request_id = rid
    return rid


def request_id(request: Request) -> str:
    """Current request id, ensuring one exists (see ``ensure_request_id``)."""
    return ensure_request_id(request)


def get_request_id(request: Request | None) -> str:
    """Read-only: request id from state/headers, or a fresh id if ``request`` is None."""
    if request is None:
        return secrets.token_hex(8)
    return ensure_request_id(request)


def incident_code(family: str = "REL-GEN") -> str:
    """Stable prefix + random suffix for support tickets / logs."""
    fam = (family or "REL-GEN").strip().upper()
    return f"{fam}-{secrets.token_hex(3).upper()}"


def emit_reliability_event(
    logger: logging.Logger,
    event: str,
    *,
    request: Request | None = None,
    **fields: Any,
) -> None:
    """Structured single-line log line with sorted keys (legacy ``emit_event`` shape)."""
    rid = get_request_id(request)
    payload: dict[str, Any] = {"event": event, "request_id": rid, **fields}
    kv = " ".join(f"{k}={payload[k]!r}" for k in sorted(payload.keys()))
    logger.info("[reliability] %s", kv)


def safe_user_error(message: str, code: str) -> str:
    """User-visible string including incident/reference code."""
    return f"{message} (incident: {code})"
