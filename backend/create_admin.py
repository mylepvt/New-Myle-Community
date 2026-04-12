#!/usr/bin/env python3
"""
Create admin user for Myle Dashboard.
"""

import asyncio
import sys
import hashlib
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.app_setting import AppSetting


def get_password_hash(password: str) -> str:
    """Simple password hashing using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


async def create_admin_user():
    """Create admin user and default settings."""
    print("Creating admin user and default settings...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if admin user exists
            from sqlalchemy import select, text
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            )
            admin_count = result.scalar()
            
            if admin_count == 0:
                # Create default admin user
                admin_user = User(
                    fbo_id="ADMIN001",
                    email="admin@myle.com",
                    username="admin",
                    role="admin",
                    hashed_password=get_password_hash("admin123"),
                    registration_status="approved",
                    training_required=False,
                    training_status="not_required",
                    access_blocked=False,
                    discipline_status="active",
                    name="System Administrator"
                )
                
                session.add(admin_user)
                await session.commit()
                print("Created default admin user: admin@myle.com / admin123")
            else:
                print("Admin user already exists")
            
            # Create default app settings
            default_settings = {
                "enable_wallet": "true",
                "enable_training": "true",
                "enable_reports": "true",
                "enable_analytics": "true",
                "enable_notifications": "true",
                "payment_amount_cents": "19600",
                "training_days_required": "7",
                "system_name": "Myle Dashboard",
                "default_language": "en",
                "default_timezone": "UTC",
                "session_timeout": "3600",
                "max_upload_size": "10485760"
            }
            
            for key, value in default_settings.items():
                # Check if setting exists
                result = await session.execute(
                    text("SELECT COUNT(*) FROM app_settings WHERE key = :key"),
                    {"key": key}
                )
                count = result.scalar()
                
                if count == 0:
                    setting = AppSetting(key=key, value=value)
                    session.add(setting)
            
            await session.commit()
            print("Created default app settings")
            
        except Exception as e:
            print(f"Error creating initial data: {e}")
            await session.rollback()
            return False
    
    return True


async def main():
    """Main function."""
    print("=== Creating Admin User ===")
    
    success = await create_admin_user()
    
    if success:
        print("=== Admin User Created Successfully ===")
        print("Login credentials:")
        print("  Email: admin@myle.com")
        print("  Password: admin123")
        return 0
    else:
        print("=== Failed to Create Admin User ===")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
