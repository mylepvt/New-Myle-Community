"""Training certificate generation and download."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.models.training_progress import TrainingProgress
from app.models.training_test_attempt import TrainingTestAttempt
from app.models.user import User
from app.services.certificate import generate_certificate_pdf

router = APIRouter()


@router.get("/training/certificate")
async def download_training_certificate(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    Generate and download training certificate PDF.
    
    Requirements:
    - User must have completed all 7 training days
    - User must have passed the training test (60% score)
    - Returns PDF file with certificate details
    """
    # Get user details
    user_row = await session.get(User, user.user_id)
    if not user_row:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check if training is completed
    if user_row.training_status != "completed":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Training not completed. Complete all training days and pass the test first.",
        )
    
    # Get training progress to verify completion
    progress_rows = await session.execute(
        select(TrainingProgress).where(
            TrainingProgress.user_id == user.user_id,
            TrainingProgress.completed.is_(True),
        )
    )
    completed_days = set(p.day_number for p in progress_rows.scalars().all())
    
    # Verify all 7 days are completed
    if not all(day in completed_days for day in range(1, 8)):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="All 7 training days must be completed before downloading certificate.",
        )
    
    # Get test attempt to verify passing score
    test_attempt = await session.execute(
        select(TrainingTestAttempt)
        .where(TrainingTestAttempt.user_id == user.user_id)
        .order_by(TrainingTestAttempt.attempted_at.desc())
    )
    latest_test = test_attempt.scalar_one_or_none()
    
    if not latest_test or not latest_test.passed:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Training test must be passed with 60% score before downloading certificate.",
        )
    
    # Get completion date (Day 7 completion)
    day7_progress = await session.execute(
        select(TrainingProgress).where(
            TrainingProgress.user_id == user.user_id,
            TrainingProgress.day_number == 7,
            TrainingProgress.completed.is_(True),
        )
    )
    day7_completion = day7_progress.scalar_one_or_none()
    
    completion_date = day7_completion.completed_at if day7_completion else datetime.now()
    
    # Generate certificate PDF
    try:
        pdf_bytes = await generate_certificate_pdf(
            username=user_row.username,
            fbo_id=user_row.fbo_id,
            completion_date=completion_date,
            test_score=latest_test.score,
            test_total=latest_test.total_questions,
        )
        
        # Return PDF as downloadable file
        filename = f"training_certificate_{user_row.username}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes)),
            },
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate certificate: {str(e)}",
        )


@router.get("/training/certificate/status")
async def get_certificate_status(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Check if user is eligible for certificate download.
    
    Returns eligibility status and any missing requirements.
    """
    # Get user details
    user_row = await session.get(User, user.user_id)
    if not user_row:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Get training progress
    progress_rows = await session.execute(
        select(TrainingProgress).where(
            TrainingProgress.user_id == user.user_id,
            TrainingProgress.completed.is_(True),
        )
    )
    completed_days = set(p.day_number for p in progress_rows.scalars().all())
    
    # Get latest test attempt
    test_attempt = await session.execute(
        select(TrainingTestAttempt)
        .where(TrainingTestAttempt.user_id == user.user_id)
        .order_by(TrainingTestAttempt.attempted_at.desc())
    )
    latest_test = test_attempt.scalar_one_or_none()
    
    # Check eligibility
    all_days_completed = all(day in completed_days for day in range(1, 8))
    test_passed = latest_test and latest_test.passed
    training_completed = user_row.training_status == "completed"
    
    eligible = all_days_completed and test_passed and training_completed
    
    return {
        "eligible": eligible,
        "requirements": {
            "all_days_completed": all_days_completed,
            "test_passed": test_passed,
            "training_completed": training_completed,
        },
        "completed_days": sorted(list(completed_days)),
        "total_days": 7,
        "latest_test_score": latest_test.score if latest_test else None,
        "latest_test_total": latest_test.total_questions if latest_test else None,
        "latest_test_passed": latest_test.passed if latest_test else False,
    }
