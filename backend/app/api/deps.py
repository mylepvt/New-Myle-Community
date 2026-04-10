"""Shared FastAPI dependencies for HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.auth_cookie import MYLE_ACCESS_COOKIE
from app.core.config import settings
from app.core.jwt_tokens import decode_access_token
from app.db.session import get_db

__all__ = ["get_db", "AuthUser", "require_auth_user"]


@dataclass(frozen=True)
class AuthUser:
    """Authenticated principal from cookie JWT (user id + role + email claims)."""

    user_id: int
    role: str
    email: str


def require_auth_user(request: Request) -> AuthUser:
    token = request.cookies.get(MYLE_ACCESS_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    payload = decode_access_token(token, settings.secret_key)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    role = payload.get("role")
    if not isinstance(role, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )
    user_id = int(sub)
    email_raw = payload.get("email")
    email = email_raw if isinstance(email_raw, str) else ""
    return AuthUser(user_id=user_id, role=role, email=email)


CurrentUser = Annotated[AuthUser, Depends(require_auth_user)]
