"""Payment proof upload and approval service."""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead


class PaymentService:
    """Payment proof processing and approval service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upload_payment_proof(self, file: UploadFile) -> str:
        """Upload payment proof file and return URL."""
        # This would integrate with your file storage service (S3, etc.)
        # For now, return a placeholder URL
        filename = f"payment_proofs/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        
        # TODO: Implement actual file upload logic
        # - Validate file size
        # - Store in S3 or local storage
        # - Return accessible URL
        
        return f"https://storage.example.com/{filename}"

    async def process_payment_proof(
        self,
        lead_id: int,
        payment_amount_cents: int,
        proof_url: str,
        notes: str | None,
        uploaded_by_user_id: int,
    ) -> Tuple[bool, str]:
        """Process uploaded payment proof."""
        # Get lead
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return False, "Lead not found"

        # Validate lead status
        if lead.status not in ["video_watched", "paid"]:
            return False, "Payment proof can only be uploaded for video_watched or paid leads"

        # Update lead with payment proof
        lead.payment_amount_cents = payment_amount_cents
        lead.payment_proof_url = proof_url
        lead.payment_proof_uploaded_at = datetime.utcnow()
        lead.payment_status = "pending_approval"
        lead.updated_at = datetime.utcnow()

        # Log activity (implement based on your activity logging system)
        await self._log_payment_activity(
            lead_id, uploaded_by_user_id, "payment_proof_uploaded", notes
        )

        await self.session.commit()
        return True, "Payment proof uploaded successfully"

    async def approve_payment_proof(
        self, lead_id: int, approved_by_user_id: int
    ) -> Tuple[bool, str]:
        """Approve payment proof."""
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return False, "Lead not found"

        if lead.payment_status != "pending_approval":
            return False, "Payment proof is not pending approval"

        # Update payment status
        lead.payment_status = "approved"
        lead.updated_at = datetime.utcnow()

        # Transition lead to paid status if not already
        if lead.status != "paid":
            lead.status = "paid"

        # Log activity
        await self._log_payment_activity(
            lead_id, approved_by_user_id, "payment_proof_approved"
        )

        await self.session.commit()
        return True, "Payment proof approved"

    async def reject_payment_proof(
        self, lead_id: int, rejection_reason: str, rejected_by_user_id: int
    ) -> Tuple[bool, str]:
        """Reject payment proof."""
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return False, "Lead not found"

        if lead.payment_status != "pending_approval":
            return False, "Payment proof is not pending approval"

        # Update payment status
        lead.payment_status = "rejected"
        lead.updated_at = datetime.utcnow()

        # Log activity
        await self._log_payment_activity(
            lead_id, rejected_by_user_id, "payment_proof_rejected", rejection_reason
        )

        await self.session.commit()
        return True, "Payment proof rejected"

    async def get_pending_payment_proofs(
        self, user_id: int, user_role: str
    ) -> List[dict]:
        """Get pending payment proofs for approval."""
        # Build query based on role
        if user_role == "admin":
            # Admin sees all pending payments
            where_clause = Lead.payment_status == "pending_approval"
        else:  # leader
            # Leader sees pending payments for their team
            # This would need to be implemented based on your user hierarchy
            where_clause = Lead.payment_status == "pending_approval"

        q = await self.session.execute(
            select(Lead).where(where_clause).order_by(Lead.payment_proof_uploaded_at.desc())
        )
        leads = q.scalars().all()

        return [
            {
                "lead_id": lead.id,
                "lead_name": lead.name,
                "payment_amount_cents": lead.payment_amount_cents,
                "payment_proof_url": lead.payment_proof_url,
                "payment_proof_uploaded_at": lead.payment_proof_uploaded_at,
                "uploaded_by_user_id": lead.assigned_to_user_id,
            }
            for lead in leads
        ]

    async def _log_payment_activity(
        self, lead_id: int, user_id: int, action: str, notes: str | None = None
    ) -> None:
        """Log payment-related activity."""
        # This would create an activity log entry
        # Implement based on your activity logging system
        pass

    async def validate_payment_amount(
        self, lead_id: int, payment_amount_cents: int
    ) -> Tuple[bool, str]:
        """Validate payment amount against expected amount."""
        # Standard enrollment fee is 19600 cents (196 rupees)
        standard_amount = 19600
        
        if payment_amount_cents < standard_amount:
            return False, f"Payment amount must be at least {standard_amount // 100} rupees"
        
        # You could add more complex validation here
        # - Check for overpayment
        # - Validate against specific track pricing
        # - Check for duplicate payments
        
        return True, "Payment amount is valid"
