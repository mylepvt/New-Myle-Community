"""Analytics surfaces — V1 stubs until events and reports are persisted."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette import status as http_status

from app.api.deps import AuthUser, require_auth_user
from app.schemas.system_surface import SystemStubResponse

router = APIRouter()


def _require_admin(user: AuthUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/activity-log", response_model=SystemStubResponse)
async def analytics_activity_log(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Admin activity feed placeholder (HTTP access logs are not queryable here yet)."""
    _require_admin(user)
    return SystemStubResponse(
        note="Structured activity will be stored and listed here; V1 does not expose access-log rows via API.",
    )


@router.get("/day-2-report", response_model=SystemStubResponse)
async def analytics_day_2_report(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Admin Day 2 test report placeholder."""
    _require_admin(user)
    return SystemStubResponse(
        note="Day 2 metrics will be computed server-side when definitions and data sources exist.",
    )
