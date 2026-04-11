from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status as http_status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_db, require_auth_user
from app.core.lead_status import LEAD_STATUS_SET
from app.core.realtime_hub import notify_topics
from app.models.activity_log import ActivityLog
from app.models.call_event import CallEvent
from app.models.lead import Lead
from app.schemas.call_events import CallEventCreate, CallEventListResponse, CallEventPublic
from app.schemas.leads import LeadCreate, LeadDetailPublic, LeadListResponse, LeadPublic, LeadUpdate
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
        phone=body.phone,
        email=body.email,
        city=body.city,
        source=body.source,
        notes=body.notes,
    )
    session.add(lead)
    await session.flush()
    log = ActivityLog(
        user_id=user.user_id,
        action="lead.created",
        entity_type="lead",
        entity_id=lead.id,
        meta={"name": lead.name, "status": lead.status},
    )
    session.add(log)
    await session.commit()
    await session.refresh(lead)
    await notify_topics("leads")
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
    await notify_topics("leads")
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
        await notify_topics("leads")
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

    # Contact fields
    if body.phone is not None:
        lead.phone = body.phone
    if body.email is not None:
        lead.email = body.email
    if body.city is not None:
        lead.city = body.city
    if body.source is not None:
        lead.source = body.source
    if body.notes is not None:
        lead.notes = body.notes

    # Call status
    if body.call_status is not None:
        lead.call_status = body.call_status

    # WhatsApp flag
    if body.whatsapp_sent is True:
        lead.whatsapp_sent_at = datetime.now(timezone.utc)
    elif body.whatsapp_sent is False:
        lead.whatsapp_sent_at = None

    # Payment status
    if body.payment_status is not None:
        lead.payment_status = body.payment_status

    # Day completion flags
    if body.day1_completed is True:
        lead.day1_completed_at = datetime.now(timezone.utc)
    elif body.day1_completed is False:
        lead.day1_completed_at = None
    if body.day2_completed is True:
        lead.day2_completed_at = datetime.now(timezone.utc)
    elif body.day2_completed is False:
        lead.day2_completed_at = None
    if body.day3_completed is True:
        lead.day3_completed_at = datetime.now(timezone.utc)
    elif body.day3_completed is False:
        lead.day3_completed_at = None

    await session.commit()
    await session.refresh(lead)
    await notify_topics("leads")
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
    await notify_topics("leads")


@router.get("/{lead_id}", response_model=LeadDetailPublic)
async def get_lead(
    lead_id: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LeadDetailPublic:
    """Fetch full detail for a single lead (respects visibility rules)."""
    lead = await _get_lead_or_404(session, lead_id)

    if lead.deleted_at is not None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found")

    vis = lead_visibility_where(user)
    if vis is not None:
        # Non-admin: must be creator or assigned
        if lead.created_by_user_id != user.user_id and lead.assigned_to_user_id != user.user_id:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return LeadDetailPublic.model_validate(lead)


@router.post(
    "/{lead_id}/calls",
    response_model=CallEventPublic,
    status_code=http_status.HTTP_201_CREATED,
)
async def log_call(
    lead_id: int,
    body: CallEventCreate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CallEventPublic:
    """Log a call event against a lead; updates call_count, last_called_at, call_status."""
    lead = await _get_lead_or_404(session, lead_id)

    if lead.deleted_at is not None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found")

    if not _can_mutate_lead(user, lead):
        # Also allow assigned user to log calls
        if lead.assigned_to_user_id != user.user_id:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")

    now = datetime.now(timezone.utc)

    event = CallEvent(
        lead_id=lead_id,
        user_id=user.user_id,
        outcome=body.outcome,
        duration_seconds=body.duration_seconds,
        notes=body.notes,
        called_at=now,
    )
    session.add(event)

    # Update lead call tracking atomically
    lead.call_count = (lead.call_count or 0) + 1
    lead.last_called_at = now
    # Map outcome to lead call_status
    outcome_to_call_status = {
        "answered": "called",
        "no_answer": "not_called",
        "busy": "not_called",
        "callback_requested": "callback_requested",
        "wrong_number": "not_called",
    }
    lead.call_status = outcome_to_call_status.get(body.outcome, "called")

    activity = ActivityLog(
        user_id=user.user_id,
        action="call.logged",
        entity_type="call_event",
        entity_id=None,  # will be updated after flush
        meta={
            "lead_id": lead_id,
            "outcome": body.outcome,
            "duration_seconds": body.duration_seconds,
        },
    )
    session.add(activity)

    await session.flush()
    # Backfill the entity_id with the newly created event id
    activity.entity_id = event.id

    await session.commit()
    await session.refresh(event)
    await notify_topics("leads")
    return CallEventPublic.model_validate(event)


@router.get("/{lead_id}/calls", response_model=CallEventListResponse)
async def list_calls(
    lead_id: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CallEventListResponse:
    """List all call events for a lead (respects visibility rules)."""
    lead = await _get_lead_or_404(session, lead_id)

    if lead.deleted_at is not None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found")

    vis = lead_visibility_where(user)
    if vis is not None:
        if lead.created_by_user_id != user.user_id and lead.assigned_to_user_id != user.user_id:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")

    count_stmt = (
        select(func.count())
        .select_from(CallEvent)
        .where(CallEvent.lead_id == lead_id)
    )
    total = int((await session.execute(count_stmt)).scalar_one())

    list_stmt = (
        select(CallEvent)
        .where(CallEvent.lead_id == lead_id)
        .order_by(CallEvent.called_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(list_stmt)).scalars().all()
    items = [CallEventPublic.model_validate(r) for r in rows]
    return CallEventListResponse(items=items, total=total)
