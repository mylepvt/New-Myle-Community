from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_OUTCOME_SET = {
    "answered",
    "no_answer",
    "busy",
    "callback_requested",
    "wrong_number",
}


class CallEventCreate(BaseModel):
    outcome: str = Field(max_length=32)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("outcome")
    @classmethod
    def outcome_allowed(cls, v: str) -> str:
        s = v.strip()
        if s not in _OUTCOME_SET:
            raise ValueError(f"Invalid outcome; must be one of {sorted(_OUTCOME_SET)}")
        return s


class CallEventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    user_id: int
    outcome: str
    duration_seconds: Optional[int]
    notes: Optional[str]
    called_at: datetime
    created_at: datetime


class CallEventListResponse(BaseModel):
    items: list[CallEventPublic]
    total: int
