import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.core.auth_context import refresh_session_identity
from app.core.auth_cookies import clear_session_cookies, issue_session_cookies
from app.core.auth_cookie import MYLE_ACCESS_COOKIE, MYLE_REFRESH_COOKIE
from app.core.config import settings
from app.core.fbo_id import normalize_fbo_id, normalize_registration_fbo_id
from app.core.jwt_tokens import decode_access_token, decode_refresh_token
from app.core.passwords import (
    hash_password,
    should_upgrade_stored_password_to_bcrypt,
    verify_password_legacy_compatible,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    DevLoginRequest,
    DevLoginResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UplineLookupResponse,
)
from app.services.dev_users import dev_email_for_role
from app.services.login_identity import (
    assert_safe_username,
    find_upline_user,
    is_fbo_digit_signature_taken,
    is_phone_taken,
    is_username_taken,
    resolve_user_by_fbo_or_username,
    validate_upline_for_team_registration,
)
from app.core.auth_login_guards import ensure_may_issue_session_cookies

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
    fbo_raw = payload.get("fbo_id")
    fbo_s = fbo_raw if isinstance(fbo_raw, str) else None
    un_raw = payload.get("username")
    un_s = un_raw if isinstance(un_raw, str) else None
    dn_raw = payload.get("display_name")
    dn_s = dn_raw if isinstance(dn_raw, str) else None
    ver_raw = payload.get("ver")
    ver_s: int | None = None
    if isinstance(ver_raw, int):
        ver_s = ver_raw
    elif isinstance(ver_raw, float) and ver_raw == int(ver_raw):
        ver_s = int(ver_raw)
    ts_raw = payload.get("training_status")
    ts_s = ts_raw if isinstance(ts_raw, str) else None
    rs_raw = payload.get("registration_status")
    rs_s = rs_raw if isinstance(rs_raw, str) else None
    tr_raw = payload.get("training_required")
    tr_b: bool | None = None
    if isinstance(tr_raw, bool):
        tr_b = tr_raw
    return MeResponse(
        authenticated=True,
        role=role,
        user_id=user_id,
        fbo_id=fbo_s,
        username=un_s,
        email=email_s,
        display_name=dn_s,
        auth_version=ver_s,
        training_status=ts_s,
        training_required=tr_b,
        registration_status=rs_s,
    )


@router.get("/lookup-upline-fbo", response_model=UplineLookupResponse)
async def lookup_upline_fbo(
    session: Annotated[AsyncSession, Depends(get_db)],
    fbo_id: Annotated[str, Query(alias="fbo_id")],
) -> UplineLookupResponse:
    """Public upline validation (legacy ``/api/lookup-upline-fbo``)."""
    raw = (fbo_id or "").strip()
    if not raw:
        return UplineLookupResponse(
            found=False,
            message="Enter an FBO ID.",
        )
    u = await find_upline_user(session, raw)
    if u is None:
        return UplineLookupResponse(
            found=False,
            message="FBO ID not found. Check the ID with your leader or admin.",
        )
    role = (u.role or "").strip().lower()
    name = (u.username or "").strip()
    st = (u.registration_status or "").strip().lower()
    if role == "team":
        return UplineLookupResponse(
            found=True,
            is_leader=False,
            is_valid_upline=False,
            message=(
                "This FBO ID belongs to a team member, not a leader or admin. "
                "Please enter your upline's FBO ID."
            ),
        )
    if role not in ("leader", "admin"):
        return UplineLookupResponse(
            found=True,
            is_leader=False,
            is_valid_upline=False,
            message="This FBO ID cannot be used as an upline for registration.",
        )
    if st != "approved":
        return UplineLookupResponse(
            found=True,
            is_leader=role == "leader",
            is_valid_upline=False,
            message="This account is not yet active. Please contact admin.",
        )
    label = "Leader" if role == "leader" else "Admin"
    return UplineLookupResponse(
        found=True,
        is_leader=True,
        is_valid_upline=True,
        upline_role=role,
        name=name or None,
        message=f"{label} verified: {name}",
    )


@router.post("/register", response_model=RegisterResponse)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """Self-serve registration — team role, pending until admin approves (legacy ``/register``)."""
    try:
        assert_safe_username(body.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    email_norm = body.email.strip().lower()
    r_dup = await session.execute(
        select(User.id).where(func.lower(User.email) == email_norm)
    )
    if r_dup.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="That email is already registered.")

    if await is_username_taken(session, body.username):
        raise HTTPException(
            status_code=400,
            detail="That username is already taken. Please choose another.",
        )

    reg_fbo = normalize_registration_fbo_id(body.fbo_id)
    fbo_stored = normalize_fbo_id(reg_fbo)
    if not fbo_stored:
        raise HTTPException(status_code=400, detail="FBO ID is required.")

    r_existing = await session.execute(select(User.id).where(User.fbo_id == fbo_stored))
    if r_existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400,
            detail="That FBO ID is already registered. Each FBO ID must be unique.",
        )
    if await is_fbo_digit_signature_taken(session, normalized_fbo_id=reg_fbo):
        raise HTTPException(
            status_code=400,
            detail="That FBO ID is already registered. Each FBO ID must be unique.",
        )

    phone = body.phone.strip()
    if await is_phone_taken(session, phone):
        raise HTTPException(
            status_code=400,
            detail="That mobile number is already registered. Please use a different number.",
        )

    upline = await find_upline_user(session, body.upline_fbo_id.strip())
    if upline is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f'Upline not found for "{body.upline_fbo_id.strip()}". '
                "Please enter your leader's or admin FBO ID or username."
            ),
        )
    ok_u, msg_u = validate_upline_for_team_registration(upline.role)
    if not ok_u:
        raise HTTPException(status_code=400, detail=f"{msg_u} Please enter a valid upline FBO ID.")

    training_required = body.is_new_joining
    training_status = "pending" if body.is_new_joining else "not_required"

    user = User(
        fbo_id=fbo_stored,
        username=body.username.strip(),
        email=email_norm,
        role="team",
        hashed_password=hash_password(body.password),
        upline_user_id=upline.id,
        registration_status="pending",
        phone=phone,
        training_required=training_required,
        training_status=training_status,
        name=body.username.strip(),
        joining_date=body.joining_date,
    )
    session.add(user)
    await session.commit()
    return RegisterResponse()


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ForgotPasswordResponse:
    """Create reset token if approved user exists (legacy ``/forgot-password``)."""
    em = body.email.strip().lower()
    r = await session.execute(
        select(User).where(
            func.lower(User.email) == em,
            User.registration_status == "approved",
        )
    )
    user = r.scalar_one_or_none()
    if user is not None and user.hashed_password:
        raw = secrets.token_urlsafe(32)
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token=raw,
                expires_at=exp,
                used=False,
            )
        )
        await session.commit()
        # Email delivery is product/ops — token persisted for admin/manual flows.
    return ForgotPasswordResponse()


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResetPasswordResponse:
    now = datetime.now(timezone.utc)
    r = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == body.token.strip())
    )
    row = r.scalar_one_or_none()
    if row is None or row.used or row.expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    ur = await session.execute(select(User).where(User.id == row.user_id))
    user = ur.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset link.")
    user.hashed_password = hash_password(body.password)
    row.used = True
    await session.commit()
    return ResetPasswordResponse()


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
    issue_session_cookies(response, user)
    return DevLoginResponse()


@router.post("/login", response_model=DevLoginResponse)
async def login_with_password(
    body: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DevLoginResponse:
    """FBO ID or username + password — legacy-compatible verification (bcrypt / Werkzeug / plain)."""
    user = await resolve_user_by_fbo_or_username(session, body.fbo_id)
    if user is None or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid FBO ID or password",
        )
    if not verify_password_legacy_compatible(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid FBO ID or password",
        )
    if should_upgrade_stored_password_to_bcrypt(user.hashed_password):
        user.hashed_password = hash_password(body.password)
        await session.commit()
        await session.refresh(user)
    ensure_may_issue_session_cookies(user)
    issue_session_cookies(response, user)
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
    ensure_may_issue_session_cookies(user)
    issue_session_cookies(response, user)
    return DevLoginResponse()


@router.post("/sync-identity", response_model=DevLoginResponse)
async def sync_identity(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth: CurrentUser,
) -> DevLoginResponse:
    """Reload the signed-in user from the database and re-issue JWT cookies."""
    ok = await refresh_session_identity(session, user_id=auth.user_id, response=response)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return DevLoginResponse()


@router.post("/logout", response_model=DevLoginResponse)
async def logout(response: Response) -> DevLoginResponse:
    clear_session_cookies(response)
    return DevLoginResponse()
