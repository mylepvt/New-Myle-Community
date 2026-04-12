"""Enhanced wallet API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WalletTransaction(BaseModel):
    """Wallet transaction representation."""
    id: int
    amount_cents: int
    amount_rupees: int
    currency: str
    note: str
    created_at: datetime


class WalletSummaryResponse(BaseModel):
    """Response for wallet summary endpoint."""
    balance_cents: int
    currency: str
    balance_rupees: int
    recent_transactions: List[WalletTransaction]
    pending_recharges: int
    monthly_spending_cents: int
    monthly_spending_rupees: int


class UserBalance(BaseModel):
    """User balance for admin overview."""
    user_id: int
    balance_cents: int
    balance_rupees: int


class WalletActivity(BaseModel):
    """Wallet activity for admin overview."""
    id: int
    user_id: int
    amount_cents: int
    amount_rupees: int
    note: str
    created_at: datetime


class WalletOverviewResponse(BaseModel):
    """Response for wallet overview endpoint (admin only)."""
    total_balance_cents: int
    total_balance_rupees: int
    user_count: int
    pending_recharge_requests: int
    top_balances: List[UserBalance]
    recent_activity: List[WalletActivity]


class LeadClaimRequest(BaseModel):
    """Request to claim a lead with wallet deduction."""
    lead_id: int = Field(..., description="Lead ID to claim")
    lead_price_cents: int = Field(..., description="Cost of lead in cents")


class LeadClaimResponse(BaseModel):
    """Response for lead claim."""
    success: bool
    message: str
    lead_id: int
    amount_deducted_cents: int
    new_balance_cents: int
    currency: str


class WalletAdjustmentRequest(BaseModel):
    """Request for manual wallet adjustment (admin only)."""
    target_user_id: int = Field(..., description="User ID to adjust")
    amount_cents: int = Field(..., description="Amount in cents (positive for credit, negative for debit)")
    note: str = Field(..., description="Reason for adjustment")


class WalletAdjustmentResponse(BaseModel):
    """Response for wallet adjustment."""
    success: bool
    message: str
    target_user_id: int
    amount_cents: int
    new_balance_cents: int
    currency: str


class RechargeRequestCreate(BaseModel):
    """Create recharge request."""
    amount_cents: int = Field(..., description="Amount in cents")
    utr_number: Optional[str] = Field(None, description="UTR transaction number")
    proof_url: Optional[str] = Field(None, description="URL to payment proof")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


class RechargeRequestResponse(BaseModel):
    """Recharge request response."""
    id: int
    user_id: int
    amount_cents: int
    amount_rupees: int
    utr_number: Optional[str]
    proof_url: Optional[str]
    status: str
    admin_note: Optional[str]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime


class RechargeReviewRequest(BaseModel):
    """Review recharge request (admin only)."""
    status: str = Field(..., description="approved or rejected")
    admin_note: Optional[str] = Field(None, description="Admin review note")


class PurchaseValidationResponse(BaseModel):
    """Response for purchase validation."""
    can_afford: bool
    message: str
    current_balance_cents: int
    current_balance_rupees: int
    required_amount_cents: int
    required_amount_rupees: int


class BalanceResponse(BaseModel):
    """Simple balance response."""
    balance_cents: int
    balance_rupees: int
