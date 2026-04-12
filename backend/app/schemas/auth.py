from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from app.constants.roles import Role


class MeResponse(BaseModel):
    """Current session — populated from cookie JWT when present."""

    authenticated: bool = False
    role: Optional[str] = Field(
        default=None,
        description="admin | leader | team when authenticated",
    )
    user_id: Optional[int] = Field(default=None, description="DB user id when JWT sub is numeric")
    fbo_id: Optional[str] = Field(
        default=None,
        description="Unique FBO ID (primary directory / login identifier)",
    )
    username: Optional[str] = Field(default=None, description="Optional display handle when present")
    email: Optional[str] = Field(default=None, description="User email from JWT when present")
    display_name: Optional[str] = Field(
        default=None,
        description="Display label (legacy session display_name / users.name); derived from username or email local-part",
    )
    auth_version: Optional[int] = Field(
        default=None,
        description="JWT claim ver — same idea as legacy AUTH_SESSION_VERSION",
    )
    training_status: Optional[str] = Field(
        default=None,
        description="Legacy training_status: not_required | pending | completed | unlocked",
    )
    training_required: Optional[bool] = Field(
        default=None,
        description="When true, user must complete training before full dashboard (legacy gate)",
    )
    registration_status: Optional[str] = Field(
        default=None,
        description="pending | approved | rejected — account approval gate",
    )


class DevLoginRequest(BaseModel):
    role: Role


class LoginRequest(BaseModel):
    """Password login: **FBO ID or username** (legacy ``/login``) + password."""

    fbo_id: str = Field(
        min_length=1,
        max_length=128,
        description="FBO ID (normalized) or exact username, same as legacy first field",
    )
    password: str = Field(min_length=1, max_length=512)


class DevLoginResponse(BaseModel):
    ok: bool = True


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=1, max_length=512)
    email: str = Field(min_length=3, max_length=320)
    fbo_id: str = Field(min_length=1, max_length=128)
    upline_fbo_id: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=10, max_length=32)
    is_new_joining: bool = False
    joining_date: Optional[date] = None


class RegisterResponse(BaseModel):
    ok: bool = True
    message: str = "Registration submitted! Your account is pending admin approval."


class UplineLookupResponse(BaseModel):
    found: bool
    is_leader: bool = False
    is_valid_upline: bool = False
    upline_role: Optional[str] = None
    name: Optional[str] = None
    message: str = ""


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ForgotPasswordResponse(BaseModel):
    ok: bool = True
    message: str = "If an account exists for this email, a reset link has been sent."


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=1, max_length=512)


class ResetPasswordResponse(BaseModel):
    ok: bool = True
