"""Ledger-backed wallet: balance from sum(lines); idempotent admin adjustments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.core.realtime_hub import notify_topics
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.models.wallet_recharge import WalletRecharge
from app.schemas.wallet import (
    WalletAdjustmentCreate,
    WalletLedgerEntryPublic,
    WalletLedgerListResponse,
    WalletRechargeCreate,
    WalletRechargeListResponse,
    WalletRechargePublic,
    WalletRechargeReview,
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
    await notify_topics("wallet", "leads")
    return WalletLedgerEntryPublic.model_validate(entry)


# ── Wallet Recharge Requests ─────────────────────────────────────────────────

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


@router.post(
    "/recharge-requests",
    response_model=WalletRechargePublic,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_recharge_request(
    body: WalletRechargeCreate,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletRechargePublic:
    """Submit a wallet recharge request; idempotent via idempotency_key."""
    # Idempotency check
    if body.idempotency_key is not None:
        existing = await session.execute(
            select(WalletRecharge).where(
                WalletRecharge.idempotency_key == body.idempotency_key,
                WalletRecharge.user_id == user.user_id,
            )
        )
        hit = existing.scalar_one_or_none()
        if hit is not None:
            return WalletRechargePublic.model_validate(hit)

    recharge = WalletRecharge(
        user_id=user.user_id,
        amount_cents=body.amount_cents,
        utr_number=body.utr_number,
        proof_url=body.proof_url,
        idempotency_key=body.idempotency_key,
        status="pending",
    )
    session.add(recharge)
    try:
        await session.commit()
        await session.refresh(recharge)
    except IntegrityError:
        await session.rollback()
        # Race condition on idempotency_key unique constraint
        if body.idempotency_key is not None:
            again = await session.execute(
                select(WalletRecharge).where(
                    WalletRecharge.idempotency_key == body.idempotency_key
                )
            )
            replay = again.scalar_one_or_none()
            if replay is not None:
                return WalletRechargePublic.model_validate(replay)
        raise

    await notify_topics("wallet")
    return WalletRechargePublic.model_validate(recharge)


@router.get("/recharge-requests", response_model=WalletRechargeListResponse)
async def list_recharge_requests(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, max_length=20, description="Filter by status"),
) -> WalletRechargeListResponse:
    """List recharge requests; admin sees all, others see only their own."""
    base_where = []
    if user.role != "admin":
        base_where.append(WalletRecharge.user_id == user.user_id)
    if status is not None and status.strip():
        base_where.append(WalletRecharge.status == status.strip())

    from sqlalchemy import and_

    cond = and_(*base_where) if base_where else None

    count_stmt = select(func.count()).select_from(WalletRecharge)
    if cond is not None:
        count_stmt = count_stmt.where(cond)
    total = int((await session.execute(count_stmt)).scalar_one())

    list_stmt = (
        select(WalletRecharge)
        .order_by(WalletRecharge.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if cond is not None:
        list_stmt = list_stmt.where(cond)

    rows = (await session.execute(list_stmt)).scalars().all()
    items = [WalletRechargePublic.model_validate(r) for r in rows]
    return WalletRechargeListResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch("/recharge-requests/{request_id}", response_model=WalletRechargePublic)
async def review_recharge_request(
    request_id: int,
    body: WalletRechargeReview,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletRechargePublic:
    """Admin-only: approve or reject a recharge request. Idempotent."""
    _require_admin(user)

    recharge = await session.get(WalletRecharge, request_id)
    if recharge is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Recharge request not found",
        )

    # Idempotent: already reviewed with same outcome
    if recharge.status in {"approved", "rejected"}:
        return WalletRechargePublic.model_validate(recharge)

    if recharge.status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review a request in status '{recharge.status}'",
        )

    now = datetime.now(timezone.utc)
    recharge.status = body.status
    recharge.admin_note = body.admin_note
    recharge.reviewed_by_user_id = user.user_id
    recharge.reviewed_at = now

    if body.status == "approved":
        idem_key = f"recharge_{recharge.id}"
        # Check idempotency before inserting ledger entry
        existing_entry = await session.execute(
            select(WalletLedgerEntry).where(WalletLedgerEntry.idempotency_key == idem_key)
        )
        if existing_entry.scalar_one_or_none() is None:
            ledger_entry = WalletLedgerEntry(
                user_id=recharge.user_id,
                amount_cents=recharge.amount_cents,
                currency="INR",
                note=f"Recharge approved #{recharge.id}",
                idempotency_key=idem_key,
                created_by_user_id=user.user_id,
            )
            session.add(ledger_entry)

    await session.commit()
    await session.refresh(recharge)
    await notify_topics("wallet")
    return WalletRechargePublic.model_validate(recharge)
