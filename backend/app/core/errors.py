"""Global API error shape and exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_payload(*, code: str, message: str, request: Request) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": _request_id(request),
        }
    }


def _http_exception_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable_entity",
        429: "too_many_requests",
    }
    return mapping.get(status_code, f"http_{status_code}")


def _normalize_detail(detail: Any) -> str:
    if detail is None:
        return "Error"
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict) and "msg" in item:
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "Error"
    return str(detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _http_exception_code(exc.status_code)
    message = _normalize_detail(exc.detail)
    body = error_payload(code=code, message=message, request=request)
    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    message = _normalize_detail(exc.errors())
    body = error_payload(code="validation_error", message=message, request=request)
    return JSONResponse(status_code=422, content=body)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    body = error_payload(
        code="internal_error",
        message="Internal server error",
        request=request,
    )
    return JSONResponse(status_code=500, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
