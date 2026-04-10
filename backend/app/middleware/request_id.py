"""Assign a stable request id for tracing (header + response)."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

MAX_INBOUND_REQUEST_ID_LEN = 128


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raw = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        if raw and len(raw) <= MAX_INBOUND_REQUEST_ID_LEN:
            rid = raw.strip()
        else:
            rid = str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
