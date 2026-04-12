"""Analytics — activity from live leads; funnel report by status."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.schemas.system_surface import SystemStubResponse
from app.schemas.analytics import (
    TeamPerformanceResponse,
    IndividualPerformanceResponse,
    LeaderboardResponse,
    SystemOverviewResponse,
    DailyTrendsResponse,
)
from app.services.shell_insights import (
    build_activity_log_snapshot,
    build_status_funnel_report,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _require_admin(user: AuthUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/activity-log", response_model=SystemStubResponse)
async def analytics_activity_log(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SystemStubResponse:
    """Admin — recent lead creations (scoped); replace with audit store when added."""
    _require_admin(user)
    return await build_activity_log_snapshot(session, user)


@router.get("/day-2-report", response_model=SystemStubResponse)
async def analytics_day_2_report(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SystemStubResponse:
    """Admin — funnel by lead status (scoped); extend when Day 2 test entities exist."""
    _require_admin(user)
    return await build_status_funnel_report(session, user)


@router.get("/team-performance", response_model=TeamPerformanceResponse)
async def get_team_performance(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> TeamPerformanceResponse:
    """Get team performance summary (leader/admin only)."""
    if user.role not in ["leader", "admin"]:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only leader and admin can view team performance",
        )
    
    service = AnalyticsService(session)
    try:
        performance = await service.get_team_performance_summary(user.user_id, days)
        return TeamPerformanceResponse(**performance)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get team performance: {str(e)}",
        )


@router.get("/individual-performance", response_model=IndividualPerformanceResponse)
async def get_individual_performance(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    target_user_id: int = Query(default=None, ge=1, description="Target user ID (admin/leader only)"),
    days: int = Query(default=30, ge=1, le=365),
) -> IndividualPerformanceResponse:
    """Get individual performance metrics."""
    # Check permissions
    target_id = target_user_id or user.user_id
    if target_user_id and target_user_id != user.user_id:
        if user.role not in ["leader", "admin"]:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only leader and admin can view others' performance",
            )
    
    service = AnalyticsService(session)
    try:
        performance = await service.get_individual_performance(target_id, days)
        return IndividualPerformanceResponse(**performance)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get individual performance: {str(e)}",
        )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> LeaderboardResponse:
    """Get performance leaderboard."""
    service = AnalyticsService(session)
    try:
        leaderboard = await service.get_leaderboard(days)
        return LeaderboardResponse(leaderboard=leaderboard, period=f"{days} days")
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get leaderboard: {str(e)}",
        )


@router.get("/system-overview", response_model=SystemOverviewResponse)
async def get_system_overview(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> SystemOverviewResponse:
    """Get system-wide analytics overview (admin only)."""
    _require_admin(user)
    
    service = AnalyticsService(session)
    try:
        overview = await service.get_system_overview(days)
        return SystemOverviewResponse(**overview)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system overview: {str(e)}",
        )


@router.get("/daily-trends", response_model=DailyTrendsResponse)
async def get_daily_trends(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    target_user_id: int = Query(default=None, ge=1, description="Target user ID for individual trends"),
    days: int = Query(default=30, ge=1, le=90),
) -> DailyTrendsResponse:
    """Get daily report trends."""
    # Check permissions for user-specific trends
    if target_user_id and target_user_id != user.user_id:
        if user.role not in ["leader", "admin"]:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only leader and admin can view others' trends",
            )
    
    target_id = target_user_id or (None if user.role in ["leader", "admin"] else user.user_id)
    
    service = AnalyticsService(session)
    try:
        trends = await service.get_daily_report_trends(target_id, days)
        return DailyTrendsResponse(trends=trends, period=f"{days} days")
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get daily trends: {str(e)}",
        )
