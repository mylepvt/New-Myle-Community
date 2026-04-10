"""Team directory and enrollment stubs (org hierarchy phased)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.models.user import User
from app.schemas.system_surface import SystemStubResponse
from app.schemas.team import (
    TeamEnrollmentListResponse,
    TeamMemberListResponse,
    TeamMemberPublic,
    TeamMyTeamResponse,
)

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


@router.get("/reports", response_model=SystemStubResponse)
async def team_reports(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="Team reports will aggregate server-side metrics when definitions exist.",
    )


@router.get("/approvals", response_model=SystemStubResponse)
async def team_approvals(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="Generic approvals queue is not persisted yet; use enrollment-requests for the INR 196 enrollment stub.",
    )
