"""Leads eligible for retargeting (non-archived, status lost or contacted)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_db, require_auth_user
from app.models.lead import Lead
from app.schemas.leads import LeadListResponse, LeadPublic
from app.services.lead_scope import lead_visibility_where

router = APIRouter()

_RETARGET_STATUSES = ("lost", "contacted")
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


@router.get("", response_model=LeadListResponse)
async def list_retarget_leads(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> LeadListResponse:
    """Scoped like ``GET /leads`` — only rows with ``status`` in lost/contacted and not archived."""
    parts = [
        Lead.status.in_(_RETARGET_STATUSES),
        Lead.archived_at.is_(None),
        Lead.deleted_at.is_(None),
        Lead.in_pool.is_(False),
    ]
    vis = lead_visibility_where(user)
    if vis is not None:
        parts.append(vis)
    cond = and_(*parts)

    count_q = select(func.count()).select_from(Lead).where(cond)
    total = int((await session.execute(count_q)).scalar_one())

    list_q = (
        select(Lead).where(cond).order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    )
    rows = (await session.execute(list_q)).scalars().all()
    items = [LeadPublic.model_validate(r) for r in rows]
    return LeadListResponse(items=items, total=total, limit=limit, offset=offset)
