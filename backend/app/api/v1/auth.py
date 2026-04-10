from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth_cookie import MYLE_ACCESS_COOKIE
from app.core.config import settings
from app.core.jwt_tokens import create_access_token, decode_access_token
from app.models.user import User
from app.schemas.auth import DevLoginRequest, DevLoginResponse, MeResponse
from app.services.dev_users import dev_email_for_role

router = APIRouter()


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
    token = create_access_token(
        sub=str(user.id),
        role=user.role,
        secret=settings.secret_key,
        email=user.email,
    )
    response.set_cookie(
        key=MYLE_ACCESS_COOKIE,
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        path="/",
        secure=settings.session_cookie_secure,
    )
    return DevLoginResponse()


@router.post("/logout", response_model=DevLoginResponse)
async def logout(response: Response) -> DevLoginResponse:
    response.delete_cookie(
        key=MYLE_ACCESS_COOKIE,
        path="/",
        samesite="lax",
        secure=settings.session_cookie_secure,
    )
    return DevLoginResponse()
