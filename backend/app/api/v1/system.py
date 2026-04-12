"""System section — training (DB-backed), coaching stubs; decision engine uses `shell_insights`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.deps import AuthUser, get_db, require_auth_user
from app.models.training_progress import TrainingProgress
from app.models.training_question import TrainingQuestion
from app.models.training_test_attempt import TrainingTestAttempt
from app.models.training_video import TrainingVideo
from app.models.user import User
from app.schemas.system_surface import (
    SystemStubResponse,
    TrainingSurfaceResponse,
)
from app.schemas.training_test import (
    MarkTrainingDayBody,
    TrainingTestQuestionPublic,
    TrainingTestResultPublic,
    TrainingTestSubmitBody,
)
from app.services.shell_insights import build_decision_engine_snapshot
from app.services.training_surface import build_training_surface

router = APIRouter()

PASS_MARK_PERCENT = 60


def _require_admin(user: AuthUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _require_admin_or_leader(user: AuthUser) -> None:
    if user.role not in ("admin", "leader"):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/training", response_model=TrainingSurfaceResponse)
async def system_training(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingSurfaceResponse:
    """7-day training catalog + caller's completion rows (legacy training home data)."""
    return await build_training_surface(session, user.user_id)


@router.post("/training/mark-day", response_model=TrainingSurfaceResponse)
async def mark_training_day(
    body: MarkTrainingDayBody,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingSurfaceResponse:
    """Mark one training day complete (legacy day-by-day). All catalog days done → training gate cleared."""
    vq = await session.execute(
        select(TrainingVideo.id).where(TrainingVideo.day_number == body.day_number)
    )
    if vq.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Invalid training day",
        )

    # Get current progress to enforce sequential and calendar rules
    current_progress = await session.execute(
        select(TrainingProgress).where(TrainingProgress.user_id == user.user_id)
    )
    progress_rows = current_progress.scalars().all()
    
    # Check sequential completion (must complete previous days first)
    if body.day_number > 1:
        previous_completed = any(
            p.day_number == body.day_number - 1 and p.completed 
            for p in progress_rows
        )
        if not previous_completed:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Complete Day {body.day_number - 1} first",
            )
    
    # Check calendar enforcement for days 2-7
    if body.day_number > 1:
        day1_progress = next((p for p in progress_rows if p.day_number == 1), None)
        if day1_progress and day1_progress.completed_at:
            days_since_day1 = (datetime.now(timezone.utc) - day1_progress.completed_at).days
            min_days_required = body.day_number - 1
            if days_since_day1 < min_days_required:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Day {body.day_number} unlocks {min_days_required} days after completing Day 1",
                )

    now = datetime.now(timezone.utc)
    existing = await session.execute(
        select(TrainingProgress).where(
            TrainingProgress.user_id == user.user_id,
            TrainingProgress.day_number == body.day_number,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.completed = True
        row.completed_at = now
    else:
        session.add(
            TrainingProgress(
                user_id=user.user_id,
                day_number=body.day_number,
                completed=True,
                completed_at=now,
            )
        )
    await session.flush()

    catalog = (
        await session.execute(
            select(TrainingVideo.day_number).order_by(TrainingVideo.day_number.asc())
        )
    ).scalars().all()
    if catalog:
        done_rows = await session.execute(
            select(TrainingProgress.day_number).where(
                TrainingProgress.user_id == user.user_id,
                TrainingProgress.completed.is_(True),
            )
        )
        done_set = set(done_rows.scalars().all())
        if all(d in done_set for d in catalog):
            urow = await session.get(User, user.user_id)
            if urow is not None:
                urow.training_status = "completed"
                urow.training_required = False

    await session.commit()
    return await build_training_surface(session, user.user_id)


@router.get("/training-test/questions", response_model=list[TrainingTestQuestionPublic])
async def training_test_questions(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TrainingTestQuestionPublic]:
    """MCQ bank for certification (answers verified server-side on submit)."""
    _ = user
    q = await session.execute(select(TrainingQuestion).order_by(TrainingQuestion.sort_order.asc()))
    rows = q.scalars().all()
    return [
        TrainingTestQuestionPublic(
            id=r.id,
            question=r.question,
            options={
                "a": r.option_a,
                "b": r.option_b,
                "c": r.option_c,
                "d": r.option_d,
            },
        )
        for r in rows
    ]


@router.post("/training-test/submit", response_model=TrainingTestResultPublic)
async def training_test_submit(
    body: TrainingTestSubmitBody,
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingTestResultPublic:
    """Score answers; pass at ``PASS_MARK_PERCENT``; persist attempt row."""
    q = await session.execute(select(TrainingQuestion).order_by(TrainingQuestion.sort_order.asc()))
    questions = q.scalars().all()
    if not questions:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No training questions configured",
        )

    total = len(questions)
    score = 0
    for tq in questions:
        raw = body.answers.get(str(tq.id))
        if raw is None:
            continue
        if raw.strip().lower() == tq.correct_answer.strip().lower():
            score += 1

    percent = int(100 * score / total) if total else 0
    passed = percent >= PASS_MARK_PERCENT
    now = datetime.now(timezone.utc)
    attempt = TrainingTestAttempt(
        user_id=user.user_id,
        score=score,
        total_questions=total,
        passed=passed,
        attempted_at=now,
    )
    session.add(attempt)
    await session.flush()

    training_completed = False
    if passed:
        urow = await session.get(User, user.user_id)
        if urow is not None:
            urow.training_status = "completed"
            urow.training_required = False
            training_completed = True

    await session.commit()
    await session.refresh(attempt)

    return TrainingTestResultPublic(
        score=score,
        total_questions=total,
        percent=percent,
        passed=passed,
        pass_mark_percent=PASS_MARK_PERCENT,
        attempted_at=attempt.attempted_at,
        training_completed=training_completed,
    )


@router.get("/decision-engine", response_model=SystemStubResponse)
async def system_decision_engine(
    user: Annotated[AuthUser, Depends(require_auth_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SystemStubResponse:
    """Admin — pipeline signals (stale new leads, pool depth)."""
    _require_admin(user)
    return await build_decision_engine_snapshot(session, user)


@router.get("/coaching", response_model=SystemStubResponse)
async def system_coaching(
    user: Annotated[AuthUser, Depends(require_auth_user)],
) -> SystemStubResponse:
    """Coaching panel data placeholder — admin and leader roles."""
    _require_admin_or_leader(user)
    return SystemStubResponse(
        note="Coaching tasks and metrics will be API-driven; V1 returns an empty list.",
    )
