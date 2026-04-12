#!/usr/bin/env python3
"""
Simple test script for the training system.
Run this when PostgreSQL is running to verify the training system works end-to-end.
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.services.training_surface import build_training_surface
from app.db.session import AsyncSessionLocal
from app.models.training_video import TrainingVideo
from app.models.training_progress import TrainingProgress
from app.models.user import User
from sqlalchemy import select


async def test_training_surface():
    """Test the training surface service."""
    print("Testing training surface service...")
    
    async with AsyncSessionLocal() as session:
        # Test with user_id 1 (should exist if seeded)
        try:
            result = await build_training_surface(session, 1)
            print(f"  Videos: {len(result.videos)}")
            print(f"  Progress: {len(result.progress)}")
            print(f"  Note: {result.note}")
            print(f"  Unlock dates: {result.unlock_dates}")
            
            # Verify we have 7 training videos
            assert len(result.videos) == 7, f"Expected 7 videos, got {len(result.videos)}"
            
            # Check video structure
            for video in result.videos:
                assert video.day_number >= 1 and video.day_number <= 7
                assert video.title, f"Video {video.day_number} missing title"
            
            print("  Training surface test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Training surface test: FAILED - {e}")
            return False


async def test_calendar_enforcement():
    """Test calendar enforcement logic."""
    print("Testing calendar enforcement...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Get user 1
            user = await session.get(User, 1)
            if not user:
                print("  User 1 not found - skipping calendar test")
                return True
            
            # Create test progress - Day 1 completed yesterday
            yesterday = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
            yesterday = yesterday.replace(day=yesterday.day - 1)
            
            progress = TrainingProgress(
                user_id=1,
                day_number=1,
                completed=True,
                completed_at=yesterday
            )
            session.add(progress)
            await session.commit()
            
            # Test training surface with calendar enforcement
            result = await build_training_surface(session, 1)
            
            # Should have unlock dates for days 2-7
            assert result.unlock_dates, "No unlock dates calculated"
            assert len(result.unlock_dates) == 6, f"Expected 6 unlock dates, got {len(result.unlock_dates)}"
            
            print("  Calendar enforcement test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Calendar enforcement test: FAILED - {e}")
            return False


async def test_training_progress():
    """Test training progress tracking."""
    print("Testing training progress...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Mark Day 1 as complete for user 1
            now = datetime.now(timezone.utc)
            
            existing = await session.execute(
                select(TrainingProgress).where(
                    TrainingProgress.user_id == 1,
                    TrainingProgress.day_number == 1,
                )
            )
            row = existing.scalar_one_or_none()
            
            if row:
                row.completed = True
                row.completed_at = now
            else:
                session.add(
                    TrainingProgress(
                        user_id=1,
                        day_number=1,
                        completed=True,
                        completed_at=now,
                    )
                )
            
            await session.commit()
            
            # Verify progress
            result = await build_training_surface(session, 1)
            day1_progress = next((p for p in result.progress if p.day_number == 1), None)
            
            assert day1_progress, "Day 1 progress not found"
            assert day1_progress.completed, "Day 1 not marked complete"
            assert day1_progress.completed_at, "Day 1 completion time not set"
            
            print("  Training progress test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Training progress test: FAILED - {e}")
            return False


async def main():
    """Run all training system tests."""
    print("Starting training system tests...")
    print("=" * 50)
    
    tests = [
        test_training_surface,
        test_calendar_enforcement,
        test_training_progress,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests PASSED! Training system is working correctly.")
        return 0
    else:
        print("Some tests FAILED. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
