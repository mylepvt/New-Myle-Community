#!/usr/bin/env python3
"""
Create all database tables for Myle Dashboard.
"""

import asyncio
import sys
from app.db.base import Base
from app.db.session import engine

# Import all models to ensure they are registered with Base
from app.models.user import User
from app.models.app_setting import AppSetting
from app.models.lead import Lead
from app.models.wallet_ledger import WalletLedgerEntry
from app.models.wallet_recharge import WalletRecharge
from app.models.daily_report import DailyReport
from app.models.daily_score import DailyScore
from app.models.training_progress import TrainingProgress
from app.models.training_question import TrainingQuestion
from app.models.training_test_attempt import TrainingTestAttempt
from app.models.training_video import TrainingVideo
from app.models.follow_up import FollowUp
from app.models.activity_log import ActivityLog
from app.models.announcement import Announcement
from app.models.call_event import CallEvent
from app.models.enroll_share_link import EnrollShareLink
from app.models.password_reset_token import PasswordResetToken


async def create_all_tables():
    """Create all database tables."""
    print("Creating all database tables...")
    
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("All tables created successfully!")
        return True
        
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False


async def main():
    """Main function."""
    print("=== Creating Database Tables ===")
    
    success = await create_all_tables()
    
    if success:
        print("=== Tables Created Successfully ===")
        return 0
    else:
        print("=== Failed to Create Tables ===")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
