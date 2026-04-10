from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.lead_status import LEAD_STATUS_SET


class LeadPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    created_by_user_id: int
    created_at: datetime
    archived_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    in_pool: bool = False


class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(default="new", max_length=32)

    @field_validator("status")
    @classmethod
    def status_allowed(cls, v: str) -> str:
        s = v.strip()
        if s not in LEAD_STATUS_SET:
            raise ValueError("Invalid lead status")
        return s


class LeadUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[str] = Field(default=None, max_length=32)
    archived: Optional[bool] = Field(
        default=None,
        description="True = archive now (sets archived_at); False = restore (clears archived_at)",
    )
    in_pool: Optional[bool] = Field(
        default=None,
        description="Admin only: release to shared pool (true) or remove from pool without assigning (false)",
    )
    restored: Optional[bool] = Field(
        default=None,
        description="Admin only: true = undo soft-delete (clears deleted_at)",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> LeadUpdate:
        if (
            self.name is None
            and self.status is None
            and self.archived is None
            and self.in_pool is None
            and self.restored is None
        ):
            raise ValueError(
                "At least one of name, status, archived, in_pool, or restored is required",
            )
        if self.restored is False:
            raise ValueError("restored must be true or omitted")
        return self

    @field_validator("status")
    @classmethod
    def status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if s not in LEAD_STATUS_SET:
            raise ValueError("Invalid lead status")
        return s


class LeadListResponse(BaseModel):
    items: list[LeadPublic]
    total: int
    limit: int
    offset: int
