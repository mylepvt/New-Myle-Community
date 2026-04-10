from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_db, require_auth_user
from app.models.follow_up import FollowUp
from app.models.lead import Lead
from app.schemas.follow_ups import (
    FollowUpCreate,
    FollowUpListResponse,
    FollowUpPublic,
    FollowUpUpdate,
)
from app.services.lead_access import require_visible_lead

router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


def _to_public(fu: FollowUp, lead_name: str) -> FollowUpPublic:
    return FollowUpPublic(
        id=fu.id,
        lead_id=fu.lead_id,
        lead_name=lead_name,
        note=fu.note,
        due_at=fu.due_at,
        completed_at=fu.completed_at,
        created_by_user_id=fu.created_by_user_id,
        created_at=fu.created_at,
    )


def _list_filters(user: AuthUser, open_only: bool):
    parts = []
    if user.role != "admin":
        parts.append(Lead.created_by_user_id == user.user_id)
    if open_only:
        parts.append(FollowUp.completed_at.is_(None))
    return parts


@router.get("", response_model=FollowUpListResponse)
async def list_follow_ups(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    open_only: bool = Query(
        default=True,
        description="If true, only rows with completed_at IS NULL",
    ),
) -> FollowUpListResponse:
    filters = _list_filters(user, open_only)

    count_q = select(func.count()).select_from(FollowUp).join(Lead, FollowUp.lead_id == Lead.id)
    for f in filters:
        count_q = count_q.where(f)
    total = int((await session.execute(count_q)).scalar_one())

    list_q = select(FollowUp, Lead.name).join(Lead, FollowUp.lead_id == Lead.id)
    for f in filters:
        list_q = list_q.where(f)
    list_q = (
        list_q.order_by(nulls_last(asc(FollowUp.due_at)), FollowUp.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(list_q)).all()
    items = [_to_public(fu, name) for fu, name in rows]
    return FollowUpListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=FollowUpPublic, status_code=status.HTTP_201_CREATED)
async def create_follow_up(
    body: FollowUpCreate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    lead = await require_visible_lead(session, user, body.lead_id)
    fu = FollowUp(
        lead_id=body.lead_id,
        note=body.note.strip(),
        due_at=body.due_at,
        created_by_user_id=user.user_id,
    )
    session.add(fu)
    await session.commit()
    await session.refresh(fu)
    return _to_public(fu, lead.name)


async def _get_follow_up_for_user(
    session: AsyncSession, user: AuthUser, follow_up_id: int
) -> tuple[FollowUp, Lead]:
    q = select(FollowUp, Lead).join(Lead, FollowUp.lead_id == Lead.id).where(FollowUp.id == follow_up_id)
    if user.role != "admin":
        q = q.where(Lead.created_by_user_id == user.user_id)
    row = (await session.execute(q)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")
    return row[0], row[1]


@router.patch("/{follow_up_id}", response_model=FollowUpPublic)
async def update_follow_up(
    follow_up_id: int,
    body: FollowUpUpdate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    fu, lead = await _get_follow_up_for_user(session, user, follow_up_id)
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No fields to update",
        )
    if "note" in patch:
        fu.note = str(patch["note"]).strip()
    if "due_at" in patch:
        fu.due_at = patch["due_at"]
    if "completed" in patch:
        if patch["completed"] is True:
            fu.completed_at = datetime.now(timezone.utc)
        else:
            fu.completed_at = None
    await session.commit()
    await session.refresh(fu)
    return _to_public(fu, lead.name)


@router.delete("/{follow_up_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_follow_up(
    follow_up_id: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    fu, _lead = await _get_follow_up_for_user(session, user, follow_up_id)
    await session.delete(fu)
    await session.commit()
