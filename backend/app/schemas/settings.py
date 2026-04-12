"""Enhanced settings API request/response schemas."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """Response for user profile."""
    id: int
    fbo_id: str
    username: Optional[str]
    email: str
    role: str
    phone: Optional[str]
    name: Optional[str]
    upline_user_id: Optional[int]
    registration_status: str
    training_required: bool
    training_status: str
    access_blocked: bool
    discipline_status: str
    joining_date: Optional[str]
    created_at: str


class UserProfileUpdateRequest(BaseModel):
    """Request for updating user profile."""
    username: Optional[str] = Field(None, min_length=3, max_length=128)
    phone: Optional[str] = Field(None, min_length=10, max_length=32)
    name: Optional[str] = Field(None, max_length=255)
    joining_date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    upline_user_id: Optional[int] = Field(None, ge=1)
    
    # Admin-only fields
    registration_status: Optional[str] = Field(None, description="Admin only")
    training_required: Optional[bool] = Field(None, description="Admin only")
    training_status: Optional[str] = Field(None, description="Admin only")
    access_blocked: Optional[bool] = Field(None, description="Admin only")
    discipline_status: Optional[str] = Field(None, description="Admin only")


class UserPreferencesResponse(BaseModel):
    """Response for user preferences."""
    email_notifications: bool
    push_notifications: bool
    daily_report_reminders: bool
    lead_assignment_alerts: bool
    payment_notifications: bool
    training_reminders: bool
    weekly_summary: bool
    language: str
    timezone: str
    theme: str


class UserPreferencesUpdateRequest(BaseModel):
    """Request for updating user preferences."""
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    daily_report_reminders: Optional[bool] = None
    lead_assignment_alerts: Optional[bool] = None
    payment_notifications: Optional[bool] = None
    training_reminders: Optional[bool] = None
    weekly_summary: Optional[bool] = None
    language: Optional[str] = Field(None, description="Language code")
    timezone: Optional[str] = Field(None, description="Timezone identifier")
    theme: Optional[str] = Field(None, description="Theme: light, dark")


class SystemDefaults(BaseModel):
    """System default configuration."""
    default_role: str
    require_training: bool
    auto_approve_registrations: bool
    default_language: str
    default_timezone: str
    session_timeout: int
    max_upload_size: int
    supported_languages: List[str]
    supported_timezones: List[str]


class FeatureFlags(BaseModel):
    """System feature flags."""
    enable_wallet: bool
    enable_training: bool
    enable_reports: bool
    enable_analytics: bool
    enable_notifications: bool


class SystemConfigurationResponse(BaseModel):
    """Response for system configuration."""
    app_settings: Dict[str, str]
    system_defaults: SystemDefaults
    feature_flags: FeatureFlags


class SystemConfigurationUpdateRequest(BaseModel):
    """Request for updating system configuration."""
    # Dynamic fields - any key-value pairs
    class Config:
        extra = "allow"


class AppSettingsResponse(BaseModel):
    """Response for application settings."""
    settings: Dict[str, str]


class AppSettingUpdateRequest(BaseModel):
    """Request for updating application setting."""
    key: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., max_length=1000)


class SystemUsersSummaryResponse(BaseModel):
    """Response for system users summary."""
    total_users: int
    by_role: Dict[str, int]
    by_status: Dict[str, int]
    blocked_users: int
    by_training_status: Dict[str, int]


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: dict[str, any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


class AuditLogResponse(BaseModel):
    """Response for audit log."""
    entries: List[AuditLogEntry]
    total: int
    limit: int
    offset: int


class UserHierarchyValidation(BaseModel):
    """User hierarchy validation result."""
    is_valid: bool
    message: str


class UserSearchRequest(BaseModel):
    """Request for user search."""
    query: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = Field(None, description="Filter by role")
    status: Optional[str] = Field(None, description="Filter by registration status")
    training_status: Optional[str] = Field(None, description="Filter by training status")
    is_blocked: Optional[bool] = Field(None, description="Filter by access status")
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class UserSearchResponse(BaseModel):
    """Response for user search."""
    users: List[UserProfileResponse]
    total: int
    limit: int
    offset: int


class PasswordChangeRequest(BaseModel):
    """Request for password change."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class PasswordChangeResponse(BaseModel):
    """Response for password change."""
    success: bool
    message: str


class EmailChangeRequest(BaseModel):
    """Request for email change."""
    new_email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    current_password: str = Field(..., min_length=1)


class EmailChangeResponse(BaseModel):
    """Response for email change."""
    success: bool
    message: str
    verification_required: bool


class NotificationSettings(BaseModel):
    """Notification settings configuration."""
    email_enabled: bool
    push_enabled: bool
    sms_enabled: bool
    in_app_enabled: bool
    default_channels: List[str]


class NotificationTemplate(BaseModel):
    """Notification template."""
    id: str
    name: str
    subject: Optional[str]
    body: str
    channels: List[str]
    enabled: bool


class NotificationSettingsResponse(BaseModel):
    """Response for notification settings."""
    settings: NotificationSettings
    templates: List[NotificationTemplate]


class BackupRequest(BaseModel):
    """Request for system backup."""
    include_user_data: bool = True
    include_reports: bool = True
    include_wallet_data: bool = True
    include_settings: bool = True


class BackupResponse(BaseModel):
    """Response for system backup."""
    success: bool
    message: str
    backup_id: Optional[str] = None
    download_url: Optional[str] = None
    file_size: Optional[int] = None


class SystemHealthResponse(BaseModel):
    """Response for system health check."""
    status: str
    database_connected: bool
    redis_connected: Optional[bool] = None
    storage_available: bool
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    uptime_seconds: Optional[int] = None
    last_check: str
