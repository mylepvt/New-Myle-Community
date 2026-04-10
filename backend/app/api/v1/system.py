"""System section stubs (training, decision engine, coaching) — empty until modeled."""

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


def _require_admin_or_leader(user: AuthUser) -> None:
    if user.role not in ("admin", "leader"):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/training", response_model=SystemStubResponse)
async def system_training(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Admin training catalog placeholder — no persistence in V1."""
    _require_admin(user)
    return SystemStubResponse(
        note="Training modules are not stored yet; this endpoint reserves the contract.",
    )


@router.get("/decision-engine", response_model=SystemStubResponse)
async def system_decision_engine(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Admin decision / rules placeholder."""
    _require_admin(user)
    return SystemStubResponse(
        note="Decision rules will be listed here when the engine is implemented server-side.",
    )


@router.get("/coaching", response_model=SystemStubResponse)
async def system_coaching(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Coaching panel data placeholder — admin and leader roles."""
    _require_admin_or_leader(user)
    return SystemStubResponse(
        note="Coaching tasks and metrics will be API-driven; V1 returns an empty list.",
    )
