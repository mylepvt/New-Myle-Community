from typing import Literal, Optional

from pydantic import BaseModel, Field


class MeResponse(BaseModel):
    """Current session — populated from cookie JWT when present."""

    authenticated: bool = False
    role: Optional[str] = Field(
        default=None,
        description="admin | leader | team when authenticated",
    )
    user_id: Optional[int] = Field(default=None, description="DB user id when JWT sub is numeric")
    email: Optional[str] = Field(default=None, description="User email from JWT when present")


class DevLoginRequest(BaseModel):
    role: Literal["admin", "leader", "team"]


class DevLoginResponse(BaseModel):
    ok: bool = True
