from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WalletLedgerEntryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    amount_cents: int
    currency: str
    note: Optional[str] = None
    created_at: datetime


class WalletSummaryResponse(BaseModel):
    balance_cents: int
    currency: str
    recent_entries: list[WalletLedgerEntryPublic]


class WalletLedgerListResponse(BaseModel):
    items: list[WalletLedgerEntryPublic]
    total: int
    limit: int
    offset: int


class WalletAdjustmentCreate(BaseModel):
    user_id: int = Field(ge=1)
    amount_cents: int
    idempotency_key: str = Field(min_length=8, max_length=128)
    note: Optional[str] = Field(default=None, max_length=512)


# ── Recharge request schemas ─────────────────────────────────────────────────

_RECHARGE_STATUS_SET = {"pending", "approved", "rejected"}


class WalletRechargeCreate(BaseModel):
    amount_cents: int = Field(ge=1)
    utr_number: Optional[str] = Field(default=None, max_length=50)
    proof_url: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class WalletRechargeReview(BaseModel):
    status: str
    admin_note: Optional[str] = Field(default=None, max_length=512)

    @field_validator("status")
    @classmethod
    def status_allowed(cls, v: str) -> str:
        s = v.strip()
        if s not in {"approved", "rejected"}:
            raise ValueError("status must be 'approved' or 'rejected'")
        return s


class WalletRechargePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    amount_cents: int
    utr_number: Optional[str]
    proof_url: Optional[str]
    status: str
    admin_note: Optional[str]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime


class WalletRechargeListResponse(BaseModel):
    items: list[WalletRechargePublic]
    total: int
    limit: int
    offset: int
