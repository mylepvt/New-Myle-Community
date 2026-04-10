"""Admin execution placeholders (at-risk, lead ledger) — not v1 product scope, nav parity only."""

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


@router.get("/at-risk-leads", response_model=SystemStubResponse)
async def execution_at_risk(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="At-risk scoring is not enabled in v1; weak members / leak map remain out of scope per roadmap.",
    )


@router.get("/lead-ledger", response_model=SystemStubResponse)
async def execution_lead_ledger(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="Lead ledger views will tie to leads + wallet when product defines rules; use Leads + Recycle bin today.",
    )
