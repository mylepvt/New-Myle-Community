"""Sliding-window rate limit for POST /api/v1/auth/login|dev-login|refresh (in-process)."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core import config
from app.core.errors import error_payload

_AUTH_POST_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/dev-login",
        "/api/v1/auth/refresh",
    }
)

_window_seconds = 60.0
_store: dict[str, list[float]] = defaultdict(list)


def _reset_rate_limit_store_for_tests() -> None:
    _store.clear()


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = config.settings.auth_login_rate_limit_per_minute
        if limit <= 0:
            return await call_next(request)
        if request.method != "POST" or request.url.path not in _AUTH_POST_PATHS:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"
        now = time.time()
        bucket = _store[key]
        cutoff = now - _window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= limit:
            body = error_payload(
                code="too_many_requests",
                message="Too many requests; try again shortly.",
                request=request,
            )
            return JSONResponse(status_code=429, content=body)
        bucket.append(now)
        return await call_next(request)
