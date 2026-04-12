"""Enhanced lead pipeline business logic services."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lead_status import (
    LEAD_STATUS_LABELS,
    LEAD_STATUS_SEQUENCE,
    TEAM_FORBIDDEN_STATUS_SLUGS,
    WORKBOARD_COLUMNS,
)
from app.core.pipeline_rules import (
    STATUS_TO_STAGE,
    TRACKS,
    validate_vl2_status_transition_for_role,
)
from app.models.lead import Lead
from app.models.user import User


class PipelineService:
    """Enhanced pipeline operations with business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_pipeline_view(self, user_id: int, user_role: str) -> Dict:
        """Get user's pipeline view based on role and hierarchy."""
        # Get user and their downline
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        # Build visibility filter based on role
        if user_role == "admin":
            where_clause = Lead.archived_at.is_(None)
        elif user_role == "leader":
            # Leader sees own leads + team leads
            team_user_ids = await self._get_team_user_ids(user_id)
            where_clause = and_(
                Lead.archived_at.is_(None),
                Lead.assigned_to_user_id.in_(team_user_ids + [user_id])
            )
        else:  # team
            where_clause = and_(
                Lead.archived_at.is_(None),
                Lead.assigned_to_user_id == user_id
            )

        # Get leads grouped by status
        leads_by_status = {}
        for status in WORKBOARD_COLUMNS:
            q = await self.session.execute(
                select(Lead)
                .where(and_(where_clause, Lead.status == status))
                .order_by(Lead.created_at.desc())
            )
            leads_by_status[status] = q.scalars().all()

        # Calculate metrics
        total_leads = sum(len(leads) for leads in leads_by_status.values())
        conversion_rate = await self._calculate_conversion_rate(user_id, user_role)

        return {
            "columns": WORKBOARD_COLUMNS,
            "leads_by_status": leads_by_status,
            "total_leads": total_leads,
            "conversion_rate": conversion_rate,
            "user_role": user_role,
            "status_labels": LEAD_STATUS_LABELS,
        }

    async def transition_lead_status(
        self,
        lead_id: int,
        target_status: str,
        user_id: int,
        user_role: str,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Transition lead status with business rule validation."""
        # Get lead
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return False, "Lead not found"

        # Check permissions
        can_access = await self._can_user_access_lead(lead, user_id, user_role)
        if not can_access:
            return False, "Access denied"

        # Validate transition
        is_valid, error_msg = validate_vl2_status_transition_for_role(
            current_slug=lead.status,
            target_slug=target_status,
            role=user_role,
        )
        if not is_valid:
            return False, error_msg

        # Apply business rules for specific transitions
        transition_result = await self._apply_transition_business_rules(
            lead, target_status, user_id, user_role
        )
        if not transition_result[0]:
            return transition_result

        # Update lead
        lead.status = target_status
        lead.updated_at = datetime.utcnow()

        # Log activity
        await self._log_status_change(lead, target_status, user_id, notes)

        await self.session.commit()
        return True, "Status updated successfully"

    async def get_available_transitions(self, lead_id: int, user_id: int, user_role: str) -> List[str]:
        """Get list of statuses user can transition this lead to."""
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return []

        can_access = await self._can_user_access_lead(lead, user_id, user_role)
        if not can_access:
            return []

        available = []
        for status in LEAD_STATUS_SEQUENCE:
            if user_role == "team" and status in TEAM_FORBIDDEN_STATUS_SLUGS:
                continue

            is_valid, _ = validate_vl2_status_transition_for_role(
                current_slug=lead.status,
                target_slug=status,
                role=user_role,
            )
            if is_valid:
                available.append(status)

        return available

    async def auto_expire_stale_leads(self) -> int:
        """Auto-expire stale leads based on SLA rules."""
        now = datetime.utcnow()
        expired_count = 0

        # Define SLA rules for each status
        sla_rules = {
            "new_lead": timedelta(days=3),
            "contacted": timedelta(days=2),
            "invited": timedelta(days=2),
            "video_sent": timedelta(days=3),
            "video_watched": timedelta(days=2),
            "day1": timedelta(days=1),
            "day2": timedelta(days=1),
            "interview": timedelta(days=2),
        }

        for status, max_age in sla_rules.items():
            cutoff = now - max_age
            
            # Find stale leads
            q = await self.session.execute(
                select(Lead)
                .where(
                    and_(
                        Lead.status == status,
                        Lead.created_at < cutoff,
                        Lead.archived_at.is_(None),
                    )
                )
            )
            stale_leads = q.scalars().all()

            # Move to retarget
            for lead in stale_leads:
                lead.status = "retarget"
                lead.updated_at = now
                expired_count += 1

        await self.session.commit()
        return expired_count

    async def get_pipeline_metrics(self, user_id: int, user_role: str) -> Dict:
        """Get comprehensive pipeline metrics."""
        # Get date range for metrics (last 30 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        # Build visibility filter
        if user_role == "admin":
            where_clause = and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date,
            )
        elif user_role == "leader":
            team_user_ids = await self._get_team_user_ids(user_id)
            where_clause = and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date,
                Lead.assigned_to_user_id.in_(team_user_ids + [user_id]),
            )
        else:  # team
            where_clause = and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date,
                Lead.assigned_to_user_id == user_id,
            )

        # Get metrics by status
        status_counts = {}
        for status in WORKBOARD_COLUMNS:
            q = await self.session.execute(
                select(func.count(Lead.id))
                .where(and_(where_clause, Lead.status == status))
            )
            status_counts[status] = q.scalar() or 0

        # Calculate conversion funnel
        total_new = status_counts.get("new_lead", 0)
        total_converted = status_counts.get("converted", 0)
        conversion_rate = (total_converted / total_new * 100) if total_new > 0 else 0

        # Payment metrics
        paid_count = status_counts.get("paid", 0)
        payment_rate = (paid_count / total_new * 100) if total_new > 0 else 0

        # Day completion metrics
        day1_count = status_counts.get("day1", 0)
        day2_count = status_counts.get("day2", 0)
        day1_rate = (day1_count / paid_count * 100) if paid_count > 0 else 0
        day2_rate = (day2_count / day1_count * 100) if day1_count > 0 else 0

        return {
            "period": "30 days",
            "status_counts": status_counts,
            "total_leads": sum(status_counts.values()),
            "conversion_rate": round(conversion_rate, 2),
            "payment_rate": round(payment_rate, 2),
            "day1_rate": round(day1_rate, 2),
            "day2_rate": round(day2_rate, 2),
            "funnel": {
                "new_leads": total_new,
                "contacted": status_counts.get("contacted", 0),
                "paid": paid_count,
                "day1": day1_count,
                "day2": day2_count,
                "converted": total_converted,
            },
        }

    async def _get_team_user_ids(self, leader_id: int) -> List[int]:
        """Get user IDs of team members under this leader."""
        # This would typically query a hierarchy table
        # For now, return empty - implement based on your user hierarchy
        return []

    async def _can_user_access_lead(self, lead: Lead, user_id: int, user_role: str) -> bool:
        """Check if user can access this lead."""
        if user_role == "admin":
            return True
        if user_role == "leader":
            # Check if lead is assigned to user or their team
            return lead.assigned_to_user_id == user_id
        if user_role == "team":
            return lead.assigned_to_user_id == user_id
        return False

    async def _apply_transition_business_rules(
        self, lead: Lead, target_status: str, user_id: int, user_role: str
    ) -> Tuple[bool, str]:
        """Apply business rules for specific status transitions."""
        # Payment validation
        if target_status == "paid":
            if not lead.payment_amount_cents or lead.payment_amount_cents <= 0:
                return False, "Payment amount required for paid status"
            if lead.payment_status != "approved":
                return False, "Payment must be approved first"

        # Day completion validation
        if target_status in ["day1", "day2"]:
            if lead.status != "paid":
                return False, f"Must be paid before {target_status}"

        # Interview validation
        if target_status == "interview":
            if lead.status != "day2":
                return False, "Must complete Day 2 before interview"

        # Conversion validation
        if target_status == "converted":
            if lead.status not in ["interview", "track_selected", "seat_hold"]:
                return False, "Invalid path to conversion"

        return True, "Business rules validated"

    async def _log_status_change(
        self, lead: Lead, new_status: str, user_id: int, notes: Optional[str]
    ) -> None:
        """Log status change for audit trail."""
        # This would create an activity log entry
        # Implement based on your activity logging system
        pass

    async def _calculate_conversion_rate(self, user_id: int, user_role: str) -> float:
        """Calculate conversion rate for user's visible leads."""
        # Get total leads and converted leads
        # This is a simplified calculation
        return 0.0
