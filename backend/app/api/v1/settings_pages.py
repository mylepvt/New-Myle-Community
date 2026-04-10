"""Settings nav stubs — general, help, all members, org tree."""

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


@router.get("/app", response_model=SystemStubResponse)
async def settings_app(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="App-wide settings will be key/value in DB; environment still comes from server config.",
    )


@router.get("/help", response_model=SystemStubResponse)
async def settings_help(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(note="Help content can be static or CMS-backed later.")


@router.get("/all-members", response_model=SystemStubResponse)
async def settings_all_members(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(
        note="For live directory use Team → Members (GET /api/v1/team/members).",
    )


@router.get("/org-tree", response_model=SystemStubResponse)
async def settings_org_tree(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    _require_admin(user)
    return SystemStubResponse(note="Org hierarchy is not modeled yet; my-team returns self-only for leaders.")
