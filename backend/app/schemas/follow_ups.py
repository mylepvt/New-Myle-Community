from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FollowUpPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    lead_name: str = Field(description="Parent lead name at read time")
    note: str
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by_user_id: int
    created_at: datetime


class FollowUpCreate(BaseModel):
    lead_id: int = Field(ge=1)
    note: str = Field(min_length=1, max_length=2000)
    due_at: Optional[datetime] = None


class FollowUpUpdate(BaseModel):
    note: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    due_at: Optional[datetime] = Field(
        default=None,
        description="Omit to leave unchanged; null clears due date",
    )
    completed: Optional[bool] = Field(
        default=None,
        description="True = mark done now; False = reopen",
    )


class FollowUpListResponse(BaseModel):
    items: list[FollowUpPublic]
    total: int
    limit: int
    offset: int
