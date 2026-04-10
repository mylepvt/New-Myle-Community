from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status as http_status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_db, require_auth_user
from app.core.lead_status import LEAD_STATUS_SET
from app.models.lead import Lead
from app.schemas.leads import LeadCreate, LeadListResponse, LeadPublic, LeadUpdate
from app.services.lead_scope import lead_visibility_where

router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


def _escape_ilike(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _lead_list_conditions(
    user: AuthUser,
    *,
    q: Optional[str],
    status_filter: Optional[str],
    archived_only: bool,
    deleted_only: bool,
):
    parts: list = []
    vis = lead_visibility_where(user)
    if vis is not None:
        parts.append(vis)
    if deleted_only:
        parts.append(Lead.deleted_at.is_not(None))
    else:
        parts.append(Lead.deleted_at.is_(None))
        parts.append(Lead.in_pool.is_(False))
        if archived_only:
            parts.append(Lead.archived_at.is_not(None))
        else:
            parts.append(Lead.archived_at.is_(None))
    if q is not None and (s := q.strip()):
        pattern = f"%{_escape_ilike(s)}%"
        parts.append(Lead.name.ilike(pattern, escape="\\"))
    if status_filter is not None:
        parts.append(Lead.status == status_filter)
    return and_(*parts) if parts else None


def _parse_status_query(raw: Optional[str]) -> Optional[str]:
    if raw is None or raw.strip() == "":
        return None
    s = raw.strip()
    if s not in LEAD_STATUS_SET:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid status filter",
        )
    return s


@router.get("", response_model=LeadListResponse)
async def list_leads(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    q: Optional[str] = Query(default=None, max_length=200, description="Case-insensitive name substring"),
    status: Optional[str] = Query(default=None, max_length=32, description="Exact status"),
    archived_only: bool = Query(
        default=False,
        description="If true, only archived leads; if false (default), only active (non-archived)",
    ),
    deleted_only: bool = Query(
        default=False,
        description="If true, soft-deleted leads (recycle bin) — admin only",
    ),
) -> LeadListResponse:
    """List leads visible to this role; admin sees all, others only their own."""
    if archived_only and deleted_only:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot combine archived_only and deleted_only",
        )
    if deleted_only and user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")

    status_f = _parse_status_query(status)
    cond = _lead_list_conditions(
        user,
        q=q,
        status_filter=status_f,
        archived_only=archived_only,
        deleted_only=deleted_only,
    )

    count_base = select(func.count()).select_from(Lead)
    if cond is not None:
        count_base = count_base.where(cond)
    total_r = await session.execute(count_base)
    total = int(total_r.scalar_one())

    list_q = select(Lead).order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    if cond is not None:
        list_q = list_q.where(cond)
    result = await session.execute(list_q)
    rows = result.scalars().all()
    items = [LeadPublic.model_validate(r) for r in rows]
    return LeadListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=LeadPublic, status_code=http_status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    lead = Lead(
        name=body.name.strip(),
        status=body.status,
        created_by_user_id=user.user_id,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return lead


async def _get_lead_or_404(session: AsyncSession, lead_id: int) -> Lead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


def _can_mutate_lead(user: AuthUser, lead: Lead) -> bool:
    return user.role == "admin" or lead.created_by_user_id == user.user_id


@router.post("/{lead_id}/claim", response_model=LeadPublic)
async def claim_lead(
    lead_id: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Take ownership of a lead in the shared pool (sets creator to you, clears in_pool)."""
    lead = await _get_lead_or_404(session, lead_id)
    if lead.deleted_at is not None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if not lead.in_pool or lead.archived_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Lead is not available in the pool",
        )
    lead.created_by_user_id = user.user_id
    lead.in_pool = False
    await session.commit()
    await session.refresh(lead)
    return lead


@router.patch("/{lead_id}", response_model=LeadPublic)
async def update_lead(
    lead_id: int,
    body: LeadUpdate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    lead = await _get_lead_or_404(session, lead_id)

    if lead.deleted_at is not None and body.restored is not True:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Lead is deleted — restore from recycle bin first (admin only)",
        )

    if body.restored is True:
        if user.role != "admin":
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")
        if lead.deleted_at is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Lead is not deleted",
            )
        lead.deleted_at = None
        await session.commit()
        await session.refresh(lead)
        return lead

    if not _can_mutate_lead(user, lead):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if body.in_pool is not None:
        if user.role != "admin":
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")
        if lead.deleted_at is not None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cannot change pool state of a deleted lead",
            )
        if body.in_pool is True:
            if lead.archived_at is not None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="Unarchive before adding to pool",
                )
        lead.in_pool = body.in_pool

    if body.name is not None:
        lead.name = body.name.strip()
    if body.status is not None:
        lead.status = body.status
    if body.archived is True:
        lead.archived_at = datetime.now(timezone.utc)
        lead.in_pool = False
    elif body.archived is False:
        lead.archived_at = None

    await session.commit()
    await session.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    lead = await _get_lead_or_404(session, lead_id)
    if not _can_mutate_lead(user, lead):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if lead.deleted_at is not None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found")
    lead.deleted_at = datetime.now(timezone.utc)
    lead.in_pool = False
    await session.commit()
