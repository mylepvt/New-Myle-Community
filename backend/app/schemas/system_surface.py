"""JSON stubs for System nav surfaces until real modules ship."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SystemStubResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    note: Optional[str] = None


class TrainingVideoRow(BaseModel):
    day_number: int
    title: str
    youtube_url: Optional[str] = None


class TrainingProgressRow(BaseModel):
    day_number: int
    completed: bool
    completed_at: Optional[datetime] = None


class TrainingSurfaceResponse(BaseModel):
    """Training home payload — catalog + per-user progress (DB-backed)."""

    videos: list[TrainingVideoRow] = Field(default_factory=list)
    progress: list[TrainingProgressRow] = Field(default_factory=list)
    note: Optional[str] = None
    unlock_dates: Optional[dict[int, str]] = Field(default=None, description="Calendar unlock dates for days 2-7")
