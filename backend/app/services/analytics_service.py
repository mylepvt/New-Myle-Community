"""Enhanced analytics and reporting business logic services."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_report import DailyReport
from app.models.daily_score import DailyScore
from app.models.lead import Lead
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry


class AnalyticsService:
    """Enhanced analytics operations with business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_team_performance_summary(
        self, leader_user_id: int, days: int = 30
    ) -> Dict:
        """Get comprehensive team performance summary for leader."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get team member IDs (simplified - implement based on your hierarchy)
        team_user_ids = await self._get_team_user_ids(leader_user_id)
        team_user_ids.append(leader_user_id)  # Include leader

        # Daily reports summary
        reports_q = await self.session.execute(
            select(
                func.count(DailyReport.id).label("total_reports"),
                func.sum(DailyReport.total_calling).label("total_calls"),
                func.sum(DailyReport.calls_picked).label("calls_picked"),
                func.sum(DailyReport.enrollments_done).label("enrollments"),
                func.sum(DailyReport.payments_actual).label("payments"),
                func.avg(DailyReport.total_calling).label("avg_daily_calls"),
            )
            .where(
                and_(
                    DailyReport.user_id.in_(team_user_ids),
                    DailyReport.report_date >= start_date,
                    DailyReport.report_date <= end_date,
                )
            )
        )
        reports_data = reports_q.first()

        # Lead performance
        leads_q = await self.session.execute(
            select(
                func.count(Lead.id).label("total_leads"),
                func.sum(func.case((Lead.status == "converted", 1), else_=0)).label("converted_leads"),
                func.sum(func.case((Lead.status == "paid", 1), else_=0)).label("paid_leads"),
            )
            .where(
                and_(
                    Lead.assigned_to_user_id.in_(team_user_ids),
                    Lead.created_at >= datetime.combine(start_date, datetime.min.time()),
                    Lead.created_at <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        leads_data = leads_q.first()

        # Score summary
        scores_q = await self.session.execute(
            select(
                func.sum(DailyScore.points).label("total_points"),
                func.avg(DailyScore.points).label("avg_daily_points"),
                func.count(DailyScore.id).label("days_with_reports"),
            )
            .where(
                and_(
                    DailyScore.user_id.in_(team_user_ids),
                    DailyScore.score_date >= start_date,
                    DailyScore.score_date <= end_date,
                )
            )
        )
        scores_data = scores_q.first()

        # Calculate rates
        total_calls = reports_data.total_calls or 0
        calls_picked = reports_data.calls_picked or 0
        total_leads = leads_data.total_leads or 0
        converted_leads = leads_data.converted_leads or 0
        paid_leads = leads_data.paid_leads or 0

        pickup_rate = (calls_picked / total_calls * 100) if total_calls > 0 else 0
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        payment_rate = (paid_leads / total_leads * 100) if total_leads > 0 else 0

        return {
            "period": f"{days} days",
            "team_size": len(team_user_ids),
            "reports": {
                "total_reports": reports_data.total_reports or 0,
                "total_calls": total_calls,
                "calls_picked": calls_picked,
                "enrollments": reports_data.enrollments or 0,
                "payments": reports_data.payments or 0,
                "avg_daily_calls": round(reports_data.avg_daily_calls or 0, 1),
                "pickup_rate": round(pickup_rate, 2),
            },
            "leads": {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "paid_leads": paid_leads,
                "conversion_rate": round(conversion_rate, 2),
                "payment_rate": round(payment_rate, 2),
            },
            "scores": {
                "total_points": scores_data.total_points or 0,
                "avg_daily_points": round(scores_data.avg_daily_points or 0, 1),
                "days_with_reports": scores_data.days_with_reports or 0,
            },
        }

    async def get_individual_performance(
        self, user_id: int, days: int = 30
    ) -> Dict:
        """Get individual performance metrics."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Daily reports
        reports_q = await self.session.execute(
            select(DailyReport)
            .where(
                and_(
                    DailyReport.user_id == user_id,
                    DailyReport.report_date >= start_date,
                    DailyReport.report_date <= end_date,
                )
            )
            .order_by(DailyReport.report_date.desc())
        )
        reports = reports_q.scalars().all()

        # Lead performance
        leads_q = await self.session.execute(
            select(
                func.count(Lead.id).label("total_leads"),
                func.sum(func.case((Lead.status == "converted", 1), else_=0)).label("converted_leads"),
                func.sum(func.case((Lead.status == "paid", 1), else_=0)).label("paid_leads"),
            )
            .where(
                and_(
                    Lead.assigned_to_user_id == user_id,
                    Lead.created_at >= datetime.combine(start_date, datetime.min.time()),
                    Lead.created_at <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        leads_data = leads_q.first()

        # Score data
        scores_q = await self.session.execute(
            select(
                func.sum(DailyScore.points).label("total_points"),
                func.count(DailyScore.id).label("days_with_reports"),
            )
            .where(
                and_(
                    DailyScore.user_id == user_id,
                    DailyScore.score_date >= start_date,
                    DailyScore.score_date <= end_date,
                )
            )
        )
        scores_data = scores_q.first()

        # Calculate daily trends
        daily_data = []
        for i in range(days):
            current_date = end_date - timedelta(days=i)
            report = next((r for r in reports if r.report_date == current_date), None)
            
            daily_data.append({
                "date": current_date.isoformat(),
                "calls": report.total_calling if report else 0,
                "enrollments": report.enrollments_done if report else 0,
                "payments": report.payments_actual if report else 0,
                "points": 20 if report else 0,  # 20 points per report
            })

        return {
            "period": f"{days} days",
            "reports": {
                "total_reports": len(reports),
                "total_calls": sum(r.total_calling for r in reports),
                "total_enrollments": sum(r.enrollments_done for r in reports),
                "total_payments": sum(r.payments_actual for r in reports),
                "avg_daily_calls": round(sum(r.total_calling for r in reports) / len(reports), 1) if reports else 0,
            },
            "leads": {
                "total_leads": leads_data.total_leads or 0,
                "converted_leads": leads_data.converted_leads or 0,
                "paid_leads": leads_data.paid_leads or 0,
            },
            "scores": {
                "total_points": scores_data.total_points or 0,
                "days_with_reports": scores_data.days_with_reports or 0,
            },
            "daily_trends": daily_data,
        }

    async def get_leaderboard(self, days: int = 30) -> List[Dict]:
        """Get performance leaderboard."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get top performers by points
        leaderboard_q = await self.session.execute(
            select(
                DailyScore.user_id,
                func.sum(DailyScore.points).label("total_points"),
                func.count(DailyScore.id).label("days_with_reports"),
            )
            .where(
                and_(
                    DailyScore.score_date >= start_date,
                    DailyScore.score_date <= end_date,
                )
            )
            .group_by(DailyScore.user_id)
            .order_by(func.sum(DailyScore.points).desc())
            .limit(20)
        )
        leaderboard_data = leaderboard_q.all()

        # Get user details
        user_ids = [row.user_id for row in leaderboard_data]
        users_q = await self.session.execute(
            select(User.id, User.username, User.fbo_id)
            .where(User.id.in_(user_ids))
        )
        users = {row.id: row for row in users_q}

        # Get additional metrics for each user
        result = []
        for row in leaderboard_data:
            user = users.get(row.user_id)
            if not user:
                continue

            # Get lead metrics
            leads_q = await self.session.execute(
                select(
                    func.count(Lead.id).label("total_leads"),
                    func.sum(func.case((Lead.status == "converted", 1), else_=0)).label("converted_leads"),
                )
                .where(
                    and_(
                        Lead.assigned_to_user_id == row.user_id,
                        Lead.created_at >= datetime.combine(start_date, datetime.min.time()),
                        Lead.created_at <= datetime.combine(end_date, datetime.max.time()),
                    )
                )
            )
            leads_data = leads_q.first()

            result.append({
                "rank": len(result) + 1,
                "user_id": row.user_id,
                "username": user.username,
                "fbo_id": user.fbo_id,
                "total_points": row.total_points,
                "days_with_reports": row.days_with_reports,
                "avg_daily_points": round(row.total_points / days, 1),
                "total_leads": leads_data.total_leads or 0,
                "converted_leads": leads_data.converted_leads or 0,
            })

        return result

    async def get_system_overview(self, days: int = 30) -> Dict:
        """Get system-wide analytics overview (admin only)."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # User activity
        active_users_q = await self.session.execute(
            select(func.count(func.distinct(DailyReport.user_id)))
            .where(
                and_(
                    DailyReport.report_date >= start_date,
                    DailyReport.report_date <= end_date,
                )
            )
        )
        active_users = active_users_q.scalar() or 0

        # Total reports and calls
        reports_q = await self.session.execute(
            select(
                func.count(DailyReport.id).label("total_reports"),
                func.sum(DailyReport.total_calling).label("total_calls"),
                func.sum(DailyReport.enrollments_done).label("total_enrollments"),
                func.sum(DailyReport.payments_actual).label("total_payments"),
            )
            .where(
                and_(
                    DailyReport.report_date >= start_date,
                    DailyReport.report_date <= end_date,
                )
            )
        )
        reports_data = reports_q.first()

        # Lead metrics
        leads_q = await self.session.execute(
            select(
                func.count(Lead.id).label("total_leads"),
                func.sum(func.case((Lead.status == "converted", 1), else_=0)).label("converted_leads"),
                func.sum(func.case((Lead.status == "paid", 1), else_=0)).label("paid_leads"),
            )
            .where(
                and_(
                    Lead.created_at >= datetime.combine(start_date, datetime.min.time()),
                    Lead.created_at <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        leads_data = leads_q.first()

        # Wallet activity
        wallet_q = await self.session.execute(
            select(
                func.count(func.distinct(WalletLedgerEntry.user_id)).label("active_wallets"),
                func.sum(func.case((WalletLedgerEntry.amount_cents > 0, WalletLedgerEntry.amount_cents), else_=0)).label("total_credits"),
                func.sum(func.case((WalletLedgerEntry.amount_cents < 0, abs(WalletLedgerEntry.amount_cents)), else_=0)).label("total_debits"),
            )
            .where(
                WalletLedgerEntry.created_at >= datetime.combine(start_date, datetime.min.time())
            )
        )
        wallet_data = wallet_q.first()

        return {
            "period": f"{days} days",
            "users": {
                "active_users": active_users,
                "total_reports": reports_data.total_reports or 0,
            },
            "reports": {
                "total_reports": reports_data.total_reports or 0,
                "total_calls": reports_data.total_calls or 0,
                "total_enrollments": reports_data.total_enrollments or 0,
                "total_payments": reports_data.total_payments or 0,
                "avg_calls_per_user": round((reports_data.total_calls or 0) / active_users, 1) if active_users > 0 else 0,
            },
            "leads": {
                "total_leads": leads_data.total_leads or 0,
                "converted_leads": leads_data.converted_leads or 0,
                "paid_leads": leads_data.paid_leads or 0,
                "conversion_rate": round((leads_data.converted_leads or 0) / (leads_data.total_leads or 1) * 100, 2),
            },
            "wallet": {
                "active_wallets": wallet_data.active_wallets or 0,
                "total_credits": wallet_data.total_cents or 0,
                "total_debits": wallet_data.total_debits or 0,
                "net_volume": (wallet_data.total_cents or 0) - (wallet_data.total_debits or 0),
            },
        }

    async def get_daily_report_trends(
        self, user_id: Optional[int] = None, days: int = 30
    ) -> List[Dict]:
        """Get daily report trends for user or team."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Build query based on user_id
        if user_id:
            where_clause = and_(
                DailyReport.user_id == user_id,
                DailyReport.report_date >= start_date,
                DailyReport.report_date <= end_date,
            )
        else:
            # Team trends - implement based on your team logic
            where_clause = and_(
                DailyReport.report_date >= start_date,
                DailyReport.report_date <= end_date,
            )

        trends_q = await self.session.execute(
            select(
                DailyReport.report_date,
                func.count(DailyReport.id).label("reports_count"),
                func.sum(DailyReport.total_calling).label("total_calls"),
                func.sum(DailyReport.enrollments_done).label("total_enrollments"),
                func.sum(DailyReport.payments_actual).label("total_payments"),
            )
            .where(where_clause)
            .group_by(DailyReport.report_date)
            .order_by(DailyReport.report_date)
        )
        trends_data = trends_q.all()

        return [
            {
                "date": row.report_date.isoformat(),
                "reports_count": row.reports_count or 0,
                "total_calls": row.total_calls or 0,
                "total_enrollments": row.total_enrollments or 0,
                "total_payments": row.total_payments or 0,
                "avg_calls_per_report": round((row.total_calls or 0) / (row.reports_count or 1), 1),
            }
            for row in trends_data
        ]

    async def _get_team_user_ids(self, leader_user_id: int) -> List[int]:
        """Get user IDs of team members under this leader."""
        # This would typically query a hierarchy table
        # For now, return empty - implement based on your user hierarchy
        return []
