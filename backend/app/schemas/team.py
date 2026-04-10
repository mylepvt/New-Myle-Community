from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TeamMemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    created_at: datetime


class TeamMemberListResponse(BaseModel):
    items: list[TeamMemberPublic]
    total: int
    limit: int
    offset: int


class TeamMyTeamResponse(BaseModel):
    """V1: only the authenticated user until org / reporting lines exist."""

    items: list[TeamMemberPublic]
    total: int


class TeamEnrollmentListResponse(BaseModel):
    """Stub for future INR 196 enrollment workflow — always empty in V1."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int
