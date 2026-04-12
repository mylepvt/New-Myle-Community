"""Issue and clear auth cookies (access + refresh JWTs). Shared by auth routes and identity refresh."""

from __future__ import annotations

from fastapi import Response

from app.core.auth_cookie import MYLE_ACCESS_COOKIE, MYLE_REFRESH_COOKIE
from app.core.config import settings
from app.core.auth_constants import AUTH_SESSION_VERSION
from app.core.jwt_tokens import create_access_token, create_refresh_token
from app.models.user import User


def display_name_from_user(user: User) -> str:
    """Legacy ``users.name`` / session ``display_name``."""
    if getattr(user, "name", None) and str(user.name).strip():
        return str(user.name).strip()
    if user.username and str(user.username).strip():
        return str(user.username).strip()
    em = (user.email or "").strip()
    if em and "@" in em:
        return em.split("@", 1)[0].strip()
    return ""


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
        "secure": settings.session_cookie_secure,
    }


def issue_session_cookies(response: Response, user: User) -> None:
    """Set short-lived access + long-lived refresh cookies from a ``User`` row."""
    dn = display_name_from_user(user)
    access = create_access_token(
        sub=str(user.id),
        role=user.role,
        secret=settings.secret_key,
        email=user.email,
        fbo_id=user.fbo_id,
        username=user.username,
        display_name=dn,
        training_status=user.training_status,
        registration_status=user.registration_status,
        training_required=user.training_required,
        ver=AUTH_SESSION_VERSION,
        minutes=settings.jwt_access_minutes,
    )
    refresh = create_refresh_token(
        sub=str(user.id),
        secret=settings.secret_key,
        days=settings.jwt_refresh_days,
    )
    kw = _cookie_kwargs()
    response.set_cookie(
        key=MYLE_ACCESS_COOKIE,
        value=access,
        max_age=settings.jwt_access_minutes * 60,
        **kw,
    )
    response.set_cookie(
        key=MYLE_REFRESH_COOKIE,
        value=refresh,
        max_age=settings.jwt_refresh_days * 24 * 3600,
        **kw,
    )


def clear_session_cookies(response: Response) -> None:
    kw = _cookie_kwargs()
    response.delete_cookie(key=MYLE_ACCESS_COOKIE, **kw)
    response.delete_cookie(key=MYLE_REFRESH_COOKIE, **kw)
