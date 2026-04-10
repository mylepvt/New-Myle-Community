from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.leads import LeadPublic


class WorkboardColumnOut(BaseModel):
    status: str = Field(description="Pipeline column key (matches Lead.status)")
    total: int = Field(description="All leads in scope with this status")
    items: list[LeadPublic] = Field(description="Newest in column, capped per limit_per_column")


class WorkboardResponse(BaseModel):
    columns: list[WorkboardColumnOut]
    max_rows_fetched: int = Field(description="Cap applied when loading recent leads for bucketing")
