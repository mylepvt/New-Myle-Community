"""Shared training catalog + user progress payload (System + Other nav)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_progress import TrainingProgress
from app.models.training_video import TrainingVideo
from app.schemas.system_surface import (
    TrainingProgressRow,
    TrainingSurfaceResponse,
    TrainingVideoRow,
)


def _calculate_unlock_dates(progress_rows: list[TrainingProgressRow]) -> Dict[int, str]:
    """Calculate unlock dates for training days based on calendar enforcement."""
    day1_completion = next((p for p in progress_rows if p.day_number == 1 and p.completed_at), None)
    
    if not day1_completion or not day1_completion.completed_at:
        return {}
    
    try:
        day1_date = datetime.fromisoformat(day1_completion.completed_at.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return {}
    
    unlock_dates = {}
    for day in range(2, 8):
        unlock_date = day1_date.date() + timedelta(days=day - 1)
        unlock_dates[day] = unlock_date.strftime('%d %b %Y')
    
    return unlock_dates


def _can_unlock_day(day_number: int, progress_rows: list[TrainingProgressRow], unlock_dates: Dict[int, str]) -> bool:
    """Check if a day can be unlocked based on calendar and sequential rules."""
    # Day 1 is always available
    if day_number == 1:
        return True
    
    # Must complete previous day
    previous_completed = any(p.day_number == day_number - 1 and p.completed for p in progress_rows)
    if not previous_completed:
        return False
    
    # Check calendar enforcement for days 2-7
    if day_number in unlock_dates:
        today = datetime.now().date()
        unlock_date_str = unlock_dates[day_number]
        try:
            unlock_date = datetime.strptime(unlock_date_str, '%d %b %Y').date()
            return today >= unlock_date
        except ValueError:
            return True  # If date parsing fails, allow access
    
    return True


async def build_training_surface(session: AsyncSession, user_id: int) -> TrainingSurfaceResponse:
    vq = await session.execute(select(TrainingVideo).order_by(TrainingVideo.day_number.asc()))
    videos = [
        TrainingVideoRow(
            day_number=v.day_number,
            title=v.title,
            youtube_url=v.youtube_url,
        )
        for v in vq.scalars().all()
    ]
    pq = await session.execute(
        select(TrainingProgress).where(TrainingProgress.user_id == user_id)
    )
    progress = [
        TrainingProgressRow(
            day_number=p.day_number,
            completed=bool(p.completed),
            completed_at=p.completed_at.isoformat() if p.completed_at else None,
        )
        for p in pq.scalars().all()
    ]
    
    # Calculate unlock dates for calendar enforcement
    unlock_dates = _calculate_unlock_dates(progress)
    
    note = None if videos else "Training catalog is empty - admin can seed `training_videos`."
    return TrainingSurfaceResponse(
        videos=videos, 
        progress=progress, 
        note=note,
        unlock_dates=unlock_dates
    )
