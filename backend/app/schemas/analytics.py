"""Analytics API request/response schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TeamPerformanceReports(BaseModel):
    """Team performance reports metrics."""
    total_reports: int
    total_calls: int
    calls_picked: int
    enrollments: int
    payments: int
    avg_daily_calls: float
    pickup_rate: float


class TeamPerformanceLeads(BaseModel):
    """Team performance leads metrics."""
    total_leads: int
    converted_leads: int
    paid_leads: int
    conversion_rate: float
    payment_rate: float


class TeamPerformanceScores(BaseModel):
    """Team performance scores metrics."""
    total_points: int
    avg_daily_points: float
    days_with_reports: int


class TeamPerformanceResponse(BaseModel):
    """Response for team performance endpoint."""
    period: str
    team_size: int
    reports: TeamPerformanceReports
    leads: TeamPerformanceLeads
    scores: TeamPerformanceScores


class IndividualPerformanceReports(BaseModel):
    """Individual performance reports metrics."""
    total_reports: int
    total_calls: int
    total_enrollments: int
    total_payments: int
    avg_daily_calls: float


class IndividualPerformanceLeads(BaseModel):
    """Individual performance leads metrics."""
    total_leads: int
    converted_leads: int
    paid_leads: int


class IndividualPerformanceScores(BaseModel):
    """Individual performance scores metrics."""
    total_points: int
    days_with_reports: int


class DailyTrendData(BaseModel):
    """Daily trend data point."""
    date: str
    calls: int
    enrollments: int
    payments: int
    points: int


class IndividualPerformanceResponse(BaseModel):
    """Response for individual performance endpoint."""
    period: str
    reports: IndividualPerformanceReports
    leads: IndividualPerformanceLeads
    scores: IndividualPerformanceScores
    daily_trends: List[DailyTrendData]


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""
    rank: int
    user_id: int
    username: str
    fbo_id: Optional[str]
    total_points: int
    days_with_reports: int
    avg_daily_points: float
    total_leads: int
    converted_leads: int


class LeaderboardResponse(BaseModel):
    """Response for leaderboard endpoint."""
    leaderboard: List[LeaderboardEntry]
    period: str


class SystemOverviewUsers(BaseModel):
    """System overview user metrics."""
    active_users: int
    total_reports: int


class SystemOverviewReports(BaseModel):
    """System overview report metrics."""
    total_reports: int
    total_calls: int
    total_enrollments: int
    total_payments: int
    avg_calls_per_user: float


class SystemOverviewLeads(BaseModel):
    """System overview lead metrics."""
    total_leads: int
    converted_leads: int
    paid_leads: int
    conversion_rate: float


class SystemOverviewWallet(BaseModel):
    """System overview wallet metrics."""
    active_wallets: int
    total_credits: int
    total_debits: int
    net_volume: int


class SystemOverviewResponse(BaseModel):
    """Response for system overview endpoint."""
    period: str
    users: SystemOverviewUsers
    reports: SystemOverviewReports
    leads: SystemOverviewLeads
    wallet: SystemOverviewWallet


class DailyTrendEntry(BaseModel):
    """Daily trend entry."""
    date: str
    reports_count: int
    total_calls: int
    total_enrollments: int
    total_payments: int
    avg_calls_per_report: float


class DailyTrendsResponse(BaseModel):
    """Response for daily trends endpoint."""
    trends: List[DailyTrendEntry]
    period: str


class ReportSubmissionRequest(BaseModel):
    """Request for daily report submission."""
    report_date: str = Field(..., description="Report date in YYYY-MM-DD format")
    total_calling: int = Field(..., ge=0, description="Total calls made")
    calls_picked: int = Field(..., ge=0, description="Calls that were picked up")
    wrong_numbers: int = Field(..., ge=0, description="Wrong number calls")
    enrollments_done: int = Field(..., ge=0, description="Enrollments completed")
    pending_enroll: int = Field(..., ge=0, description="Pending enrollments")
    underage: int = Field(..., ge=0, description="Underage contacts")
    plan_2cc: int = Field(..., ge=0, description="2CC plans")
    seat_holdings: int = Field(..., ge=0, description="Seat holdings")
    leads_educated: int = Field(..., ge=0, description="Leads educated")
    pdf_covered: int = Field(..., ge=0, description="PDFs covered")
    videos_sent_actual: int = Field(..., ge=0, description="Videos actually sent")
    calls_made_actual: int = Field(..., ge=0, description="Calls actually made")
    payments_actual: int = Field(..., ge=0, description="Payments actually received")
    remarks: Optional[str] = Field(None, description="Additional remarks")


class ReportSubmissionResponse(BaseModel):
    """Response for daily report submission."""
    success: bool
    message: str
    points_awarded: int
    report_id: int


class ReportValidationResponse(BaseModel):
    """Response for report validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ExportRequest(BaseModel):
    """Request for data export."""
    export_type: str = Field(..., description="Type of export: reports, leads, wallet")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    format: str = Field(default="csv", description="Export format: csv, xlsx, pdf")
    user_id: Optional[int] = Field(None, description="Specific user ID (admin/leader only)")


class ExportResponse(BaseModel):
    """Response for data export."""
    success: bool
    message: str
    download_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
