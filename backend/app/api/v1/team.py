"""Team directory and enrollment stubs (org hierarchy phased)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.core.fbo_id import normalize_fbo_id
from app.core.passwords import hash_password
from app.models.user import User
from app.schemas.system_surface import SystemStubResponse
from app.schemas.team import (
    PendingRegistrationsResponse,
    PendingRegistrationItem,
    RegistrationDecisionBody,
    TeamEnrollmentListResponse,
    TeamMemberCreate,
    TeamMemberListResponse,
    TeamMemberPublic,
    TeamMyTeamResponse,
    TeamReportsLiveSummary,
    TeamReportsResponse,
)
from app.services.team_reports_metrics import IST, compute_live_summary

router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


def _require_admin(user: AuthUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _require_leader(user: AuthUser) -> None:
    if user.role != "leader":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _require_admin_or_leader(user: AuthUser) -> None:
    if user.role not in ("admin", "leader"):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/members", response_model=TeamMemberListResponse)
async def list_team_members(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> TeamMemberListResponse:
    """All users (no passwords) — admin only."""
    _require_admin(user)

    count_q = select(func.count()).select_from(User)
    total = int((await session.execute(count_q)).scalar_one())

    list_q = (
        select(User).order_by(User.created_at.asc()).limit(limit).offset(offset)
    )
    rows = (await session.execute(list_q)).scalars().all()
    items = [TeamMemberPublic.model_validate(r) for r in rows]
    return TeamMemberListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/members",
    response_model=TeamMemberPublic,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_team_member(
    body: TeamMemberCreate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMemberPublic:
    """Create a user (password login). Admin only — complements ``scripts/create_user.py`` for HTTP flows."""
    _require_admin(user)
    fbo_n = normalize_fbo_id(body.fbo_id)
    dup_fbo = await session.execute(select(User.id).where(User.fbo_id == fbo_n))
    if dup_fbo.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="FBO ID already registered",
        )
    email_n = body.email.strip().lower()
    dup = await session.execute(select(User.id).where(User.email == email_n))
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    un = body.username.strip() if body.username and body.username.strip() else None
    row = User(
        fbo_id=fbo_n,
        username=un,
        email=email_n,
        role=body.role,
        hashed_password=hash_password(body.password),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="FBO ID or email already registered",
        ) from None
    await session.refresh(row)
    return TeamMemberPublic.model_validate(row)


@router.get("/my-team", response_model=TeamMyTeamResponse)
async def my_team(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMyTeamResponse:
    """Leader-only; V1 returns only your own row until reporting lines are modeled."""
    _require_leader(user)

    row = await session.get(User, user.user_id)
    if row is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")
    return TeamMyTeamResponse(items=[TeamMemberPublic.model_validate(row)], total=1)


@router.get("/enrollment-requests", response_model=TeamEnrollmentListResponse)
async def list_enrollment_requests(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> TeamEnrollmentListResponse:
    """Placeholder for INR 196 enrollment queue — empty until product adds persistence."""
    _require_admin_or_leader(user)
    return TeamEnrollmentListResponse(items=[], total=0, limit=limit, offset=offset)


def _parse_report_date_param(raw: Optional[str]) -> date:
    if raw is None or not str(raw).strip():
        return datetime.now(IST).date()
    s = str(raw).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid date; use YYYY-MM-DD",
        ) from e


@router.get("/reports", response_model=TeamReportsResponse)
async def team_reports(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    date: Optional[str] = Query(
        default=None,
        description="Calendar day YYYY-MM-DD (Asia/Kolkata); default today",
    ),
) -> TeamReportsResponse:
    """Admin — live pipeline metrics (legacy team reports top row)."""
    _require_admin(user)
    d = _parse_report_date_param(date)
    live = await compute_live_summary(session, d)
    return TeamReportsResponse(
        date=d.isoformat(),
        live_summary=TeamReportsLiveSummary(**live),
        note=(
            "Tiles use pool claims, call events, payment proof timestamps, and active pipeline counts. "
            "Per-user daily report lines also exist (POST /api/v1/reports/daily) and feed leaderboard scoring."
        ),
    )


@router.get("/pending-registrations", response_model=PendingRegistrationsResponse)
async def list_pending_registrations(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PendingRegistrationsResponse:
    """Admin — self-serve signups awaiting approval (legacy ``/admin/approvals``)."""
    _require_admin(user)
    q = await session.execute(
        select(User)
        .where(User.registration_status == "pending")
        .order_by(User.created_at.asc())
    )
    rows = q.scalars().all()
    items = [PendingRegistrationItem.model_validate(r) for r in rows]
    return PendingRegistrationsResponse(items=items, total=len(items))


@router.post("/pending-registrations/{target_user_id}/decision")
async def decide_pending_registration(
    target_user_id: int,
    body: RegistrationDecisionBody,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_admin(user)
    row = await session.get(User, target_user_id)
    if row is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")
    st = (row.registration_status or "").strip().lower()
    if st != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="User is not pending approval",
        )
    if body.action == "approve":
        row.registration_status = "approved"
    else:
        row.registration_status = "rejected"
    await session.commit()
    return {"ok": True, "registration_status": row.registration_status}


@router.get("/approvals", response_model=SystemStubResponse)
async def team_approvals(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        items=[
            {
                "title": "Pending registrations",
                "detail": "Use Team → Approvals for the full list (GET /api/v1/team/pending-registrations).",
                "href": "team/approvals",
            },
            {
                "title": "₹196 enrollment queue",
                "detail": "Enrollment proof + approvals: Team → ₹196 Approvals.",
                "href": "team/enrollment-approvals",
            },
        ],
        total=2,
        note="Registration approve/reject is on the Approvals page; this endpoint stays for shell parity.",
    )
