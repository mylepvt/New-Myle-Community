"""Enhanced wallet business logic services."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.models.wallet_recharge import WalletRecharge


class WalletService:
    """Enhanced wallet operations with business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_balance(self, user_id: int) -> Tuple[int, str]:
        """Get current wallet balance for user."""
        # Get currency
        cur_stmt = (
            select(WalletLedgerEntry.currency)
            .where(WalletLedgerEntry.user_id == user_id)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(1)
        )
        cur_r = await self.session.execute(cur_stmt)
        currency = cur_r.scalar_one_or_none() or "INR"

        # Calculate balance
        sum_stmt = select(func.coalesce(func.sum(WalletLedgerEntry.amount_cents), 0)).where(
            WalletLedgerEntry.user_id == user_id,
        )
        bal = int((await self.session.execute(sum_stmt)).scalar_one())
        return bal, currency

    async def can_afford_lead_claim(self, user_id: int, lead_price_cents: int) -> Tuple[bool, str]:
        """Check if user can afford to claim a lead."""
        balance, currency = await self.get_balance(user_id)
        
        if balance < lead_price_cents:
            deficit = lead_price_cents - balance
            return False, f"Insufficient balance. Need {deficit // 100} rupees more."
        
        return True, "Sufficient balance"

    async def deduct_for_lead_claim(
        self, user_id: int, lead_id: int, lead_price_cents: int
    ) -> Tuple[bool, str]:
        """Deduct wallet balance for lead claim."""
        # Check balance first
        can_afford, message = await self.can_afford_lead_claim(user_id, lead_price_cents)
        if not can_afford:
            return False, message

        # Get lead details
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return False, "Lead not found"

        if lead.assigned_to_user_id != user_id:
            return False, "Lead not assigned to user"

        # Create ledger entry for deduction
        idem_key = f"lead_claim_{lead_id}_{user_id}_{datetime.utcnow().isoformat()}"
        
        ledger_entry = WalletLedgerEntry(
            user_id=user_id,
            amount_cents=-lead_price_cents,  # Negative for deduction
            currency="INR",
            note=f"Lead claim deduction - Lead #{lead_id} ({lead.name})",
            idempotency_key=idem_key,
            created_by_user_id=user_id,
        )
        
        self.session.add(ledger_entry)
        await self.session.commit()
        
        return True, f"Successfully deducted {lead_price_cents // 100} rupees for lead claim"

    async def refund_for_lead_return(
        self, user_id: int, lead_id: int, lead_price_cents: int, reason: str
    ) -> Tuple[bool, str]:
        """Refund wallet balance when lead is returned to pool."""
        # Create ledger entry for refund
        idem_key = f"lead_refund_{lead_id}_{user_id}_{datetime.utcnow().isoformat()}"
        
        ledger_entry = WalletLedgerEntry(
            user_id=user_id,
            amount_cents=lead_price_cents,  # Positive for refund
            currency="INR",
            note=f"Lead refund - Lead #{lead_id} ({reason})",
            idempotency_key=idem_key,
            created_by_user_id=user_id,
        )
        
        self.session.add(ledger_entry)
        await self.session.commit()
        
        return True, f"Successfully refunded {lead_price_cents // 100} rupees"

    async def get_wallet_summary(self, user_id: int) -> Dict:
        """Get comprehensive wallet summary."""
        balance, currency = await self.get_balance(user_id)
        
        # Get recent transactions
        recent_q = (
            select(WalletLedgerEntry)
            .where(WalletLedgerEntry.user_id == user_id)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(10)
        )
        recent = (await self.session.execute(recent_q)).scalars().all()
        
        # Get pending recharge requests
        pending_q = (
            select(WalletRecharge)
            .where(and_(
                WalletRecharge.user_id == user_id,
                WalletRecharge.status == "pending"
            ))
            .order_by(WalletRecharge.created_at.desc())
        )
        pending = (await self.session.execute(pending_q)).scalars().all()
        
        # Calculate monthly spending
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spending_q = (
            select(func.coalesce(func.sum(WalletLedgerEntry.amount_cents), 0))
            .where(and_(
                WalletLedgerEntry.user_id == user_id,
                WalletLedgerEntry.amount_cents < 0,  # Deductions only
                WalletLedgerEntry.created_at >= month_start
            ))
        )
        monthly_spending = int((await self.session.execute(spending_q)).scalar_one() or 0)
        
        return {
            "balance_cents": balance,
            "currency": currency,
            "balance_rupees": balance // 100,
            "recent_transactions": [
                {
                    "id": entry.id,
                    "amount_cents": entry.amount_cents,
                    "amount_rupees": entry.amount_cents // 100,
                    "currency": entry.currency,
                    "note": entry.note,
                    "created_at": entry.created_at,
                }
                for entry in recent
            ],
            "pending_recharges": len(pending),
            "monthly_spending_cents": monthly_spending,
            "monthly_spending_rupees": monthly_spending // 100,
        }

    async def get_admin_wallet_overview(self) -> Dict:
        """Get admin overview of all wallets."""
        # Total balance across all users
        total_balance_q = select(func.coalesce(func.sum(WalletLedgerEntry.amount_cents), 0))
        total_balance = int((await self.session.execute(total_balance_q)).scalar_one() or 0)
        
        # User balances
        user_balances_q = (
            select(
                WalletLedgerEntry.user_id,
                func.sum(WalletLedgerEntry.amount_cents).label("balance")
            )
            .group_by(WalletLedgerEntry.user_id)
            .order_by(func.sum(WalletLedgerEntry.amount_cents).desc())
        )
        user_balances = (await self.session.execute(user_balances_q)).all()
        
        # Pending recharge requests
        pending_q = select(func.count()).where(WalletRecharge.status == "pending")
        pending_count = int((await self.session.execute(pending_q)).scalar_one() or 0)
        
        # Recent activity
        recent_q = (
            select(WalletLedgerEntry)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(20)
        )
        recent = (await self.session.execute(recent_q)).scalars().all()
        
        return {
            "total_balance_cents": total_balance,
            "total_balance_rupees": total_balance // 100,
            "user_count": len(user_balances),
            "pending_recharge_requests": pending_count,
            "top_balances": [
                {
                    "user_id": ub.user_id,
                    "balance_cents": ub.balance,
                    "balance_rupees": ub.balance // 100,
                }
                for ub in user_balances[:10]
            ],
            "recent_activity": [
                {
                    "id": entry.id,
                    "user_id": entry.user_id,
                    "amount_cents": entry.amount_cents,
                    "amount_rupees": entry.amount_cents // 100,
                    "note": entry.note,
                    "created_at": entry.created_at,
                }
                for entry in recent
            ],
        }

    async def validate_transaction(
        self, user_id: int, amount_cents: int, note: str
    ) -> Tuple[bool, str]:
        """Validate transaction before processing."""
        # Check amount limits
        if amount_cents == 0:
            return False, "Amount cannot be zero"
        
        if abs(amount_cents) > 10000000:  # 100,000 rupees limit
            return False, "Amount exceeds maximum limit"
        
        # Check user exists
        user = await self.session.get(User, user_id)
        if not user:
            return False, "User not found"
        
        # For deductions, check sufficient balance
        if amount_cents < 0:
            balance, _ = await self.get_balance(user_id)
            if balance < abs(amount_cents):
                return False, "Insufficient balance"
        
        # Validate note
        if not note or len(note.strip()) == 0:
            return False, "Note is required"
        
        if len(note) > 500:
            return False, "Note too long"
        
        return True, "Transaction validated"

    async def create_manual_adjustment(
        self, admin_user_id: int, target_user_id: int, amount_cents: int, note: str
    ) -> Tuple[bool, str]:
        """Create manual wallet adjustment (admin only)."""
        # Validate admin user
        admin_user = await self.session.get(User, admin_user_id)
        if not admin_user or admin_user.role != "admin":
            return False, "Only admin can make manual adjustments"
        
        # Validate transaction
        is_valid, message = await self.validate_transaction(target_user_id, amount_cents, note)
        if not is_valid:
            return False, message
        
        # Create ledger entry
        idem_key = f"manual_adj_{target_user_id}_{admin_user_id}_{datetime.utcnow().isoformat()}"
        
        ledger_entry = WalletLedgerEntry(
            user_id=target_user_id,
            amount_cents=amount_cents,
            currency="INR",
            note=f"Manual adjustment by admin: {note}",
            idempotency_key=idem_key,
            created_by_user_id=admin_user_id,
        )
        
        self.session.add(ledger_entry)
        await self.session.commit()
        
        action = "credited" if amount_cents > 0 else "debited"
        return True, f"Successfully {action} {abs(amount_cents) // 100} rupees"
