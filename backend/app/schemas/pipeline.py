"""Pipeline API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineLead(BaseModel):
    """Lead representation in pipeline view."""
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    status: str
    created_at: datetime
    assigned_to_user_id: Optional[int] = None
    payment_status: Optional[str] = None
    call_status: Optional[str] = None


class PipelineViewResponse(BaseModel):
    """Response for pipeline view endpoint."""
    columns: List[str]
    leads_by_status: Dict[str, List[PipelineLead]]
    total_leads: int
    conversion_rate: float
    user_role: str
    status_labels: Dict[str, str]


class PipelineTransitionRequest(BaseModel):
    """Request to transition lead status."""
    lead_id: int = Field(..., description="Lead ID to transition")
    target_status: str = Field(..., description="Target status")
    notes: Optional[str] = Field(None, description="Transition notes")


class StatusTransitionResponse(BaseModel):
    """Response for status transition."""
    success: bool
    message: str
    new_status: str


class PipelineMetricsResponse(BaseModel):
    """Response for pipeline metrics."""
    period: str
    status_counts: Dict[str, int]
    total_leads: int
    conversion_rate: float
    payment_rate: float
    day1_rate: float
    day2_rate: float
    funnel: Dict[str, int]


class PaymentProofRequest(BaseModel):
    """Request to upload payment proof."""
    lead_id: int = Field(..., description="Lead ID")
    payment_amount_cents: int = Field(..., description="Payment amount in cents")
    proof_url: str = Field(..., description="URL to payment proof image/document")
    notes: Optional[str] = Field(None, description="Additional notes")


class PaymentProofResponse(BaseModel):
    """Response for payment proof upload."""
    success: bool
    message: str
    payment_status: str


class BatchUpdateRequest(BaseModel):
    """Request to batch update leads."""
    lead_ids: List[int] = Field(..., description="List of lead IDs to update")
    updates: dict[str, Any] = Field(..., description="Updates to apply")


class BatchUpdateResponse(BaseModel):
    """Response for batch update."""
    success: bool
    message: str
    updated_count: int
    failed_count: int
    errors: List[str] = Field(default_factory=list)


class LeadDetailResponse(BaseModel):
    """Detailed lead information."""
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    payment_status: Optional[str] = None
    payment_amount_cents: Optional[int] = None
    payment_proof_url: Optional[str] = None
    payment_proof_uploaded_at: Optional[datetime] = None
    call_status: Optional[str] = None
    call_count: int = 0
    last_called_at: Optional[datetime] = None
    whatsapp_sent_at: Optional[datetime] = None
    day1_completed_at: Optional[datetime] = None
    day2_completed_at: Optional[datetime] = None
    d1_morning: bool = False
    d1_afternoon: bool = False
    d1_evening: bool = False
    d2_morning: bool = False
    d2_afternoon: bool = False
    d2_evening: bool = False
    no_response_attempt_count: int = 0


class CallEventCreate(BaseModel):
    """Create call event request."""
    lead_id: int = Field(..., description="Lead ID")
    call_status: str = Field(..., description="Call status")
    notes: Optional[str] = Field(None, description="Call notes")
    next_follow_up_at: Optional[datetime] = Field(None, description="Next follow up time")


class CallEventResponse(BaseModel):
    """Call event response."""
    success: bool
    message: str
    call_status: str
    follow_up_scheduled: bool = False
