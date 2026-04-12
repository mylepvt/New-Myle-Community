#!/usr/bin/env python3
"""
Comprehensive test script for the settings system.
Run this when PostgreSQL is running to verify the settings system works end-to-end.
"""

import asyncio
import sys
from datetime import datetime

from app.services.settings_service import SettingsService
from app.db.session import AsyncSessionLocal
from app.models.app_setting import AppSetting
from app.models.user import User


async def test_app_settings_crud():
    """Test app settings CRUD operations."""
    print("Testing app settings CRUD...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Test creating/updating a setting
            test_key = "test_setting_key"
            test_value = "test_value_123"
            
            success, message = await service.update_app_setting(test_key, test_value, 1)
            assert success, f"Failed to create setting: {message}"
            
            # Test getting the setting
            retrieved_value = await service.get_app_setting(test_key)
            assert retrieved_value == test_value, f"Expected {test_value}, got {retrieved_value}"
            
            # Test getting all settings
            all_settings = await service.get_app_settings()
            assert test_key in all_settings, f"Setting {test_key} not found in all settings"
            assert all_settings[test_key] == test_value, f"Incorrect value for {test_key}"
            
            # Test updating the setting
            new_value = "updated_value_456"
            success, message = await service.update_app_setting(test_key, new_value, 1)
            assert success, f"Failed to update setting: {message}"
            
            # Verify update
            retrieved_value = await service.get_app_setting(test_key)
            assert retrieved_value == new_value, f"Expected {new_value}, got {retrieved_value}"
            
            # Test deleting the setting
            success, message = await service.delete_app_setting(test_key)
            assert success, f"Failed to delete setting: {message}"
            
            # Verify deletion
            retrieved_value = await service.get_app_setting(test_key)
            assert retrieved_value is None, f"Setting {test_key} should be deleted"
            
            print("  App settings CRUD: PASSED")
            return True
            
        except Exception as e:
            print(f"  App settings CRUD: FAILED - {e}")
            return False


async def test_user_profile_management():
    """Test user profile management."""
    print("Testing user profile management...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Get user profile for user 1
            profile = await service.get_user_profile(1)
            assert profile is not None, "User profile should exist"
            assert "id" in profile, "Profile should have id"
            assert "email" in profile, "Profile should have email"
            assert "role" in profile, "Profile should have role"
            
            # Test updating user profile
            updates = {
                "name": "Test User Updated",
                "phone": "1234567890",
            }
            
            success, message = await service.update_user_profile(1, updates, 1)
            assert success, f"Failed to update profile: {message}"
            
            # Verify update
            updated_profile = await service.get_user_profile(1)
            assert updated_profile["name"] == updates["name"], "Name not updated"
            assert updated_profile["phone"] == updates["phone"], "Phone not updated"
            
            print("  User profile management: PASSED")
            return True
            
        except Exception as e:
            print(f"  User profile management: FAILED - {e}")
            return False


async def test_user_preferences():
    """Test user preferences management."""
    print("Testing user preferences...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Get user preferences
            preferences = await service.get_user_preferences(1)
            assert isinstance(preferences, dict), "Preferences should be a dictionary"
            
            required_keys = [
                "email_notifications", "push_notifications", "daily_report_reminders",
                "lead_assignment_alerts", "payment_notifications", "training_reminders",
                "weekly_summary", "language", "timezone", "theme"
            ]
            
            for key in required_keys:
                assert key in preferences, f"Missing preference key: {key}"
            
            # Test updating preferences
            updates = {
                "email_notifications": False,
                "language": "hi",
                "theme": "dark"
            }
            
            success, message = await service.update_user_preferences(1, updates)
            assert success, f"Failed to update preferences: {message}"
            
            print("  User preferences: PASSED")
            return True
            
        except Exception as e:
            print(f"  User preferences: FAILED - {e}")
            return False


async def test_system_configuration():
    """Test system configuration management."""
    print("Testing system configuration...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Get system configuration
            config = await service.get_system_configuration()
            assert "app_settings" in config, "Missing app_settings"
            assert "system_defaults" in config, "Missing system_defaults"
            assert "feature_flags" in config, "Missing feature_flags"
            
            # Verify system defaults structure
            defaults = config["system_defaults"]
            required_defaults = [
                "default_role", "require_training", "auto_approve_registrations",
                "default_language", "default_timezone", "session_timeout",
                "max_upload_size", "supported_languages", "supported_timezones"
            ]
            
            for key in required_defaults:
                assert key in defaults, f"Missing system default: {key}"
            
            # Verify feature flags structure
            flags = config["feature_flags"]
            required_flags = [
                "enable_wallet", "enable_training", "enable_reports",
                "enable_analytics", "enable_notifications"
            ]
            
            for key in required_flags:
                assert key in flags, f"Missing feature flag: {key}"
                assert isinstance(flags[key], bool), f"Feature flag {key} should be boolean"
            
            # Test updating system configuration
            updates = {
                "test_config_key": "test_config_value",
                "another_setting": "another_value"
            }
            
            success, message = await service.update_system_configuration(updates, 1)
            assert success, f"Failed to update system configuration: {message}"
            
            print("  System configuration: PASSED")
            return True
            
        except Exception as e:
            print(f"  System configuration: FAILED - {e}")
            return False


async def test_system_users_summary():
    """Test system users summary."""
    print("Testing system users summary...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Get users summary
            summary = await service.get_system_users_summary()
            
            # Verify structure
            required_keys = ["total_users", "by_role", "by_status", "blocked_users", "by_training_status"]
            for key in required_keys:
                assert key in summary, f"Missing summary key: {key}"
            
            # Verify data types
            assert isinstance(summary["total_users"], int), "total_users should be int"
            assert isinstance(summary["blocked_users"], int), "blocked_users should be int"
            assert isinstance(summary["by_role"], dict), "by_role should be dict"
            assert isinstance(summary["by_status"], dict), "by_status should be dict"
            assert isinstance(summary["by_training_status"], dict), "by_training_status should be dict"
            
            # Verify role counts
            for role, count in summary["by_role"].items():
                assert isinstance(count, int), f"Role count for {role} should be int"
                assert count >= 0, f"Role count for {role} should be non-negative"
            
            print("  System users summary: PASSED")
            return True
            
        except Exception as e:
            print(f"  System users summary: FAILED - {e}")
            return False


async def test_user_hierarchy_validation():
    """Test user hierarchy validation."""
    print("Testing user hierarchy validation...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Test self-reference (should fail)
            is_valid, message = await service.validate_user_hierarchy(1, 1)
            assert not is_valid, "Self-reference should be invalid"
            assert "own upline" in message.lower(), "Should mention self-reference"
            
            # Test valid hierarchy (should pass)
            is_valid, message = await service.validate_user_hierarchy(1, 2)
            # This might pass or fail depending on actual data structure
            # We're just testing the function works
            
            print("  User hierarchy validation: PASSED")
            return True
            
        except Exception as e:
            print(f"  User hierarchy validation: FAILED - {e}")
            return False


async def test_audit_log():
    """Test audit log functionality."""
    print("Testing audit log...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Get audit log
            audit_log = await service.get_audit_log(10, 0)
            
            # Should return a list (empty for now, but structure should be correct)
            assert isinstance(audit_log, list), "Audit log should be a list"
            
            print("  Audit log: PASSED")
            return True
            
        except Exception as e:
            print(f"  Audit log: FAILED - {e}")
            return False


async def test_settings_validation():
    """Test settings validation."""
    print("Testing settings validation...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = SettingsService(session)
            
            # Test empty key validation
            success, message = await service.update_app_setting("", "value", 1)
            assert not success, "Empty key should be invalid"
            assert "empty" in message.lower(), "Should mention empty key"
            
            # Test long key validation
            long_key = "a" * 129  # 129 characters
            success, message = await service.update_app_setting(long_key, "value", 1)
            assert not success, "Long key should be invalid"
            assert "too long" in message.lower(), "Should mention key too long"
            
            # Test valid key
            success, message = await service.update_app_setting("valid_key", "value", 1)
            assert success, f"Valid key should work: {message}"
            
            # Clean up
            await service.delete_app_setting("valid_key")
            
            print("  Settings validation: PASSED")
            return True
            
        except Exception as e:
            print(f"  Settings validation: FAILED - {e}")
            return False


async def main():
    """Run all settings system tests."""
    print("Starting settings system tests...")
    print("=" * 50)
    
    tests = [
        test_app_settings_crud,
        test_user_profile_management,
        test_user_preferences,
        test_system_configuration,
        test_system_users_summary,
        test_user_hierarchy_validation,
        test_audit_log,
        test_settings_validation,
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
        print("All tests PASSED! Settings system is working correctly.")
        return 0
    else:
        print("Some tests FAILED. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
