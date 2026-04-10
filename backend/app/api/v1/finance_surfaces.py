"""Finance nav stubs (recharges use wallet POST separately; these are read placeholders)."""

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


def _require_leader_or_team(user: AuthUser) -> None:
    if user.role not in ("leader", "team"):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/recharges", response_model=SystemStubResponse)
async def finance_recharges_stub(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="Use POST /api/v1/wallet/adjustments to credit a user with an idempotency key; this screen is the FE entry.",
    )


@router.get("/budget-export", response_model=SystemStubResponse)
async def finance_budget_export(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(note="Budget export will generate files server-side when defined.")


@router.get("/monthly-targets", response_model=SystemStubResponse)
async def finance_monthly_targets(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(note="Monthly targets table not created yet.")


@router.get("/lead-pool", response_model=SystemStubResponse)
async def finance_lead_pool_purchase(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Distinct from operational lead pool — purchase / billing stub."""
    _require_leader_or_team(user)
    return SystemStubResponse(
        note="Paid lead-pool purchases will debit wallet + grant credits when billing rules exist; use Work → Lead pool for claiming.",
    )
