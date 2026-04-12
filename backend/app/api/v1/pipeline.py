"""Enhanced lead pipeline API endpoints."""

from __future__ import annotations

from typing import Annotated, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_db, require_auth_user
from app.core.lead_status import LEAD_STATUS_LABELS, WORKBOARD_COLUMNS
from app.schemas.pipeline import (
    PipelineMetricsResponse,
    PipelineTransitionRequest,
    PipelineViewResponse,
    StatusTransitionResponse,
)
from app.services.pipeline_service import PipelineService

router = APIRouter()


@router.get("/pipeline/view", response_model=PipelineViewResponse)
async def get_pipeline_view(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineViewResponse:
    """Get user's pipeline view with leads grouped by status."""
    service = PipelineService(session)
    try:
        pipeline_data = await service.get_pipeline_view(user.user_id, user.role)
        return PipelineViewResponse(
            columns=pipeline_data["columns"],
            leads_by_status={
                status: [
                    {
                        "id": lead.id,
                        "name": lead.name,
                        "phone": lead.phone,
                        "email": lead.email,
                        "city": lead.city,
                        "status": lead.status,
                        "created_at": lead.created_at,
                        "assigned_to_user_id": lead.assigned_to_user_id,
                        "payment_status": lead.payment_status,
                        "call_status": lead.call_status,
                    }
                    for lead in leads
                ]
                for status, leads in pipeline_data["leads_by_status"].items()
            },
            total_leads=pipeline_data["total_leads"],
            conversion_rate=pipeline_data["conversion_rate"],
            user_role=pipeline_data["user_role"],
            status_labels=pipeline_data["status_labels"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pipeline view: {str(e)}",
        )


@router.post("/pipeline/transition", response_model=StatusTransitionResponse)
async def transition_lead_status(
    request: PipelineTransitionRequest,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StatusTransitionResponse:
    """Transition a lead to a new status with business rule validation."""
    service = PipelineService(session)
    try:
        success, message = await service.transition_lead_status(
            lead_id=request.lead_id,
            target_status=request.target_status,
            user_id=user.user_id,
            user_role=user.role,
            notes=request.notes,
        )
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        
        return StatusTransitionResponse(
            success=True,
            message=message,
            new_status=request.target_status,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transition lead: {str(e)}",
        )


@router.get("/pipeline/leads/{lead_id}/transitions", response_model=List[str])
async def get_available_transitions(
    lead_id: int,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> List[str]:
    """Get list of statuses user can transition this lead to."""
    service = PipelineService(session)
    try:
        transitions = await service.get_available_transitions(
            lead_id=lead_id,
            user_id=user.user_id,
            user_role=user.role,
        )
        return transitions
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transitions: {str(e)}",
        )


@router.get("/pipeline/metrics", response_model=PipelineMetricsResponse)
async def get_pipeline_metrics(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> PipelineMetricsResponse:
    """Get comprehensive pipeline metrics."""
    service = PipelineService(session)
    try:
        metrics = await service.get_pipeline_metrics(user.user_id, user.role)
        return PipelineMetricsResponse(
            period=f"{days} days",
            status_counts=metrics["status_counts"],
            total_leads=metrics["total_leads"],
            conversion_rate=metrics["conversion_rate"],
            payment_rate=metrics["payment_rate"],
            day1_rate=metrics["day1_rate"],
            day2_rate=metrics["day2_rate"],
            funnel=metrics["funnel"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}",
        )


@router.post("/pipeline/auto-expire")
async def auto_expire_stale_leads(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Dict[str, int]:
    """Auto-expire stale leads (admin/leader only)."""
    if user.role not in ["admin", "leader"]:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only admin and leader can auto-expire leads",
        )
    
    service = PipelineService(session)
    try:
        expired_count = await service.auto_expire_stale_leads()
        return {"expired_count": expired_count}
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to auto-expire leads: {str(e)}",
        )


@router.get("/pipeline/statuses")
async def get_pipeline_statuses() -> Dict[str, str]:
    """Get all available pipeline statuses with labels."""
    return LEAD_STATUS_LABELS


@router.get("/pipeline/columns")
async def get_pipeline_columns() -> List[str]:
    """Get workboard column order."""
    return WORKBOARD_COLUMNS
