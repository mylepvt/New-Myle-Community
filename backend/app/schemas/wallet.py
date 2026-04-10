from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
