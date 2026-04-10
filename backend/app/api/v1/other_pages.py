"""Other nav: leaderboard, notices, live session, training, daily report — shared stubs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette import status as http_status

from app.api.deps import AuthUser, require_auth_user
from app.schemas.system_surface import SystemStubResponse

router = APIRouter()


def _require_leader_or_team(user: AuthUser) -> None:
    if user.role not in ("leader", "team"):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/leaderboard", response_model=SystemStubResponse)
async def other_leaderboard(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _ = user
    return SystemStubResponse(note="Leaderboard rankings are not computed in v1.")


@router.get("/notice-board", response_model=SystemStubResponse)
async def other_notice_board(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _ = user
    return SystemStubResponse(note="Org notices will be stored and listed here when added.")


@router.get("/live-session", response_model=SystemStubResponse)
async def other_live_session(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _ = user
    return SystemStubResponse(note="Live session scheduling / links are not integrated in v1.")


@router.get("/training", response_model=SystemStubResponse)
async def other_training(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_leader_or_team(user)
    return SystemStubResponse(note="Member training progress will appear here; see System → Training (admin) for admin stub.")


@router.get("/daily-report", response_model=SystemStubResponse)
async def other_daily_report(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_leader_or_team(user)
    return SystemStubResponse(note="Daily report generation is not scheduled in v1.")
