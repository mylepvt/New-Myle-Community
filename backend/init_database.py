#!/usr/bin/env python3
"""
Database initialization script for Myle Dashboard.
Creates database, tables, and initial data.
"""

import asyncio
import sys
from sqlalchemy import text
from app.db.session import engine
from app.db.base import Base


async def create_database():
    """Create database and tables."""
    print("Creating database tables...")
    
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("Database tables created successfully!")
        
        # Create initial data
        await create_initial_data()
        
    except Exception as e:
        print(f"Error creating database: {e}")
        return False
    
    return True


async def create_initial_data():
    """Create initial data for the system."""
    print("Creating initial data...")
    
    from app.models.user import User
    from app.models.app_setting import AppSetting
    from app.db.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if admin user exists
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            )
            admin_count = result.scalar()
            
            if admin_count == 0:
                # Create default admin user
                from app.core.security import get_password_hash
                
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
    """Main initialization function."""
    print("=== Myle Dashboard Database Initialization ===")
    
    try:
        # Test database connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Database connection: OK")
        
        # Create database and tables
        success = await create_database()
        
        if success:
            print("\n=== Database Initialization Complete ===")
            print("Default admin user created:")
            print("  Email: admin@myle.com")
            print("  Password: admin123")
            print("\nYou can now start the backend server:")
            print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
            return 0
        else:
            print("Database initialization failed")
            return 1
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
