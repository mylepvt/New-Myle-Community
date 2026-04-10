"""JSON stubs for System nav surfaces until real modules ship."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SystemStubResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    note: Optional[str] = None
