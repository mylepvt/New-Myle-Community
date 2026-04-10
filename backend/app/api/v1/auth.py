from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth_cookie import MYLE_ACCESS_COOKIE, MYLE_REFRESH_COOKIE
from app.core.config import settings
from app.core.jwt_tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.core.passwords import verify_password
from app.models.user import User
from app.schemas.auth import DevLoginRequest, DevLoginResponse, LoginRequest, MeResponse
from app.services.dev_users import dev_email_for_role

router = APIRouter()


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
        "secure": settings.session_cookie_secure,
    }


def _set_session_cookies(response: Response, user: User) -> None:
    access = create_access_token(
        sub=str(user.id),
        role=user.role,
        secret=settings.secret_key,
        email=user.email,
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


def _clear_session_cookies(response: Response) -> None:
    kw = _cookie_kwargs()
    response.delete_cookie(key=MYLE_ACCESS_COOKIE, **kw)
    response.delete_cookie(key=MYLE_REFRESH_COOKIE, **kw)


@router.get("/me", response_model=MeResponse)
async def read_me(request: Request) -> MeResponse:
    token = request.cookies.get(MYLE_ACCESS_COOKIE)
    if not token:
        return MeResponse()
    payload = decode_access_token(token, settings.secret_key)
    if not payload:
        return MeResponse()
    role = payload.get("role")
    if not isinstance(role, str):
        return MeResponse()
    user_id = None
    sub = payload.get("sub")
    if isinstance(sub, str) and sub.isdigit():
        user_id = int(sub)
    email = payload.get("email")
    email_s = email if isinstance(email, str) else None
    return MeResponse(authenticated=True, role=role, user_id=user_id, email=email_s)


@router.post("/dev-login", response_model=DevLoginResponse)
async def dev_login(
    body: DevLoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DevLoginResponse:
    if not settings.auth_dev_login_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    email = dev_email_for_role(body.role)
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=500,
            detail="Dev user missing; run database migrations",
        )
    _set_session_cookies(response, user)
    return DevLoginResponse()


@router.post("/login", response_model=DevLoginResponse)
async def login_with_password(
    body: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DevLoginResponse:
    """Email + password; user must have ``hashed_password`` set (see migrations / admin tooling)."""
    email = body.email.strip().lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    _set_session_cookies(response, user)
    return DevLoginResponse()


@router.post("/refresh", response_model=DevLoginResponse)
async def refresh_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DevLoginResponse:
    raw = request.cookies.get(MYLE_REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )
    payload = decode_refresh_token(raw, settings.secret_key)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    uid = int(sub)
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    _set_session_cookies(response, user)
    return DevLoginResponse()


@router.post("/logout", response_model=DevLoginResponse)
async def logout(response: Response) -> DevLoginResponse:
    _clear_session_cookies(response)
    return DevLoginResponse()
