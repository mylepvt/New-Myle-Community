"""Enhanced wallet API endpoints with lead claiming integration."""

from __future__ import annotations

from typing import Annotated, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_db, require_auth_user
from app.schemas.wallet_enhanced import (
    LeadClaimRequest,
    LeadClaimResponse,
    WalletAdjustmentRequest,
    WalletAdjustmentResponse,
    WalletOverviewResponse,
    WalletSummaryResponse,
)
from app.services.wallet_service import WalletService

router = APIRouter()


@router.get("/enhanced/summary", response_model=WalletSummaryResponse)
async def get_wallet_summary(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletSummaryResponse:
    """Get comprehensive wallet summary for current user."""
    service = WalletService(session)
    try:
        summary = await service.get_wallet_summary(user.user_id)
        return WalletSummaryResponse(
            balance_cents=summary["balance_cents"],
            currency=summary["currency"],
            balance_rupees=summary["balance_rupees"],
            recent_transactions=summary["recent_transactions"],
            pending_recharges=summary["pending_recharges"],
            monthly_spending_cents=summary["monthly_spending_cents"],
            monthly_spending_rupees=summary["monthly_spending_rupees"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get wallet summary: {str(e)}",
        )


@router.get("/enhanced/overview", response_model=WalletOverviewResponse)
async def get_wallet_overview(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletOverviewResponse:
    """Get admin overview of all wallets (admin only)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only admin can view wallet overview",
        )
    
    service = WalletService(session)
    try:
        overview = await service.get_admin_wallet_overview()
        return WalletOverviewResponse(
            total_balance_cents=overview["total_balance_cents"],
            total_balance_rupees=overview["total_balance_rupees"],
            user_count=overview["user_count"],
            pending_recharge_requests=overview["pending_recharge_requests"],
            top_balances=overview["top_balances"],
            recent_activity=overview["recent_activity"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get wallet overview: {str(e)}",
        )


@router.post("/enhanced/lead-claim", response_model=LeadClaimResponse)
async def claim_lead_with_wallet(
    request: LeadClaimRequest,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LeadClaimResponse:
    """Claim a lead and deduct cost from wallet."""
    service = WalletService(session)
    try:
        # Check if user can afford the lead
        can_afford, message = await service.can_afford_lead_claim(
            user.user_id, request.lead_price_cents
        )
        if not can_afford:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        
        # Deduct from wallet
        success, message = await service.deduct_for_lead_claim(
            user.user_id, request.lead_id, request.lead_price_cents
        )
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        
        # Get new balance
        new_balance, currency = await service.get_balance(user.user_id)
        
        return LeadClaimResponse(
            success=True,
            message=message,
            lead_id=request.lead_id,
            amount_deducted_cents=request.lead_price_cents,
            new_balance_cents=new_balance,
            currency=currency,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim lead: {str(e)}",
        )


@router.post("/enhanced/manual-adjustment", response_model=WalletAdjustmentResponse)
async def create_manual_adjustment(
    request: WalletAdjustmentRequest,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WalletAdjustmentResponse:
    """Create manual wallet adjustment (admin only)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only admin can make manual adjustments",
        )
    
    service = WalletService(session)
    try:
        success, message = await service.create_manual_adjustment(
            admin_user_id=user.user_id,
            target_user_id=request.target_user_id,
            amount_cents=request.amount_cents,
            note=request.note,
        )
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        
        # Get new balance
        new_balance, currency = await service.get_balance(request.target_user_id)
        
        return WalletAdjustmentResponse(
            success=True,
            message=message,
            target_user_id=request.target_user_id,
            amount_cents=request.amount_cents,
            new_balance_cents=new_balance,
            currency=currency,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create adjustment: {str(e)}",
        )


@router.post("/enhanced/lead-refund")
async def refund_lead_to_pool(
    lead_id: int,
    refund_amount_cents: int,
    reason: str,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Dict[str, str]:
    """Refund wallet when lead is returned to pool (admin/leader only)."""
    if user.role not in ["admin", "leader"]:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only admin and leader can refund leads",
        )
    
    service = WalletService(session)
    try:
        success, message = await service.refund_for_lead_return(
            user.user_id, lead_id, refund_amount_cents, reason
        )
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        
        return {"success": "true", "message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refund lead: {str(e)}",
        )


@router.get("/enhanced/balance")
async def get_current_balance(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Dict[str, int]:
    """Get current wallet balance."""
    service = WalletService(session)
    try:
        balance, currency = await service.get_balance(user.user_id)
        return {
            "balance_cents": balance,
            "balance_rupees": balance // 100,
        }
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get balance: {str(e)}",
        )


@router.post("/enhanced/validate-purchase", response_model=None)
async def validate_purchase(
    amount_cents: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, any]:
    """Validate if user can afford a purchase."""
    service = WalletService(session)
    try:
        can_afford, message = await service.can_afford_lead_claim(user.user_id, amount_cents)
        balance, currency = await service.get_balance(user.user_id)
        
        return {
            "can_afford": can_afford,
            "message": message,
            "current_balance_cents": balance,
            "current_balance_rupees": balance // 100,
            "required_amount_cents": amount_cents,
            "required_amount_rupees": amount_cents // 100,
        }
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate purchase: {str(e)}",
        )
