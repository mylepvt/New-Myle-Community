"""Ledger-backed wallet: balance from sum(lines); idempotent admin adjustments."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.schemas.wallet import (
    WalletAdjustmentCreate,
    WalletLedgerEntryPublic,
    WalletLedgerListResponse,
    WalletSummaryResponse,
)

router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50
_RECENT = 10


def _require_admin(user: AuthUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def _balance_for_user(session: AsyncSession, user_id: int) -> tuple[int, str]:
    cur_stmt = (
        select(WalletLedgerEntry.currency)
        .where(WalletLedgerEntry.user_id == user_id)
        .order_by(WalletLedgerEntry.created_at.desc())
        .limit(1)
    )
    cur_r = await session.execute(cur_stmt)
    currency = cur_r.scalar_one_or_none() or "INR"

    sum_stmt = select(func.coalesce(func.sum(WalletLedgerEntry.amount_cents), 0)).where(
        WalletLedgerEntry.user_id == user_id,
    )
    bal = int((await session.execute(sum_stmt)).scalar_one())
    return bal, currency


@router.get("/me", response_model=WalletSummaryResponse)
async def wallet_me(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletSummaryResponse:
    """Current user's balance and last few ledger lines."""
    bal, currency = await _balance_for_user(session, user.user_id)
    recent_q = (
        select(WalletLedgerEntry)
        .where(WalletLedgerEntry.user_id == user.user_id)
        .order_by(WalletLedgerEntry.created_at.desc())
        .limit(_RECENT)
    )
    rows = (await session.execute(recent_q)).scalars().all()
    return WalletSummaryResponse(
        balance_cents=bal,
        currency=currency,
        recent_entries=[WalletLedgerEntryPublic.model_validate(r) for r in rows],
    )


@router.get("/ledger", response_model=WalletLedgerListResponse)
async def wallet_ledger(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[int] = Query(default=None, ge=1, description="Admin only: filter to this user"),
) -> WalletLedgerListResponse:
    """Paginated ledger for self, or for another user when admin."""
    target_uid = user.user_id
    if user_id is not None:
        _require_admin(user)
        target_uid = user_id

    count_stmt = select(func.count()).select_from(WalletLedgerEntry).where(
        WalletLedgerEntry.user_id == target_uid,
    )
    total = int((await session.execute(count_stmt)).scalar_one())

    list_q = (
        select(WalletLedgerEntry)
        .where(WalletLedgerEntry.user_id == target_uid)
        .order_by(WalletLedgerEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(list_q)).scalars().all()
    items = [WalletLedgerEntryPublic.model_validate(r) for r in rows]
    return WalletLedgerListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/adjustments", response_model=WalletLedgerEntryPublic, status_code=http_status.HTTP_201_CREATED)
async def wallet_create_adjustment(
    body: WalletAdjustmentCreate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletLedgerEntryPublic:
    """Admin-only credit/debit (signed amount_cents). Idempotent via idempotency_key."""
    _require_admin(user)

    existing = await session.execute(
        select(WalletLedgerEntry).where(WalletLedgerEntry.idempotency_key == body.idempotency_key),
    )
    hit = existing.scalar_one_or_none()
    if hit is not None:
        return WalletLedgerEntryPublic.model_validate(hit)

    target = await session.get(User, body.user_id)
    if target is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")

    entry = WalletLedgerEntry(
        user_id=body.user_id,
        amount_cents=body.amount_cents,
        currency="INR",
        idempotency_key=body.idempotency_key,
        note=body.note,
        created_by_user_id=user.user_id,
    )
    session.add(entry)
    try:
        await session.commit()
        await session.refresh(entry)
    except IntegrityError:
        await session.rollback()
        again = await session.execute(
            select(WalletLedgerEntry).where(WalletLedgerEntry.idempotency_key == body.idempotency_key),
        )
        replay = again.scalar_one_or_none()
        if replay is None:
            raise
        entry = replay
    return WalletLedgerEntryPublic.model_validate(entry)
