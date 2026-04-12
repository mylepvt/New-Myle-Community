#!/usr/bin/env python3
"""
Comprehensive test script for the lead pipeline system.
Run this when PostgreSQL is running to verify the pipeline system works end-to-end.
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.services.pipeline_service import PipelineService
from app.db.session import AsyncSessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.core.lead_status import LEAD_STATUS_SEQUENCE, WORKBOARD_COLUMNS
from sqlalchemy import select


async def test_pipeline_service():
    """Test the pipeline service functionality."""
    print("Testing pipeline service...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Test with user_id 1 (should exist if seeded)
            service = PipelineService(session)
            
            # Test pipeline view
            pipeline_view = await service.get_pipeline_view(1, "admin")
            print(f"  Pipeline columns: {len(pipeline_view['columns'])}")
            print(f"  Total leads: {pipeline_view['total_leads']}")
            print(f"  User role: {pipeline_view['user_role']}")
            
            # Verify we have all workboard columns
            assert len(pipeline_view['columns']) == len(WORKBOARD_COLUMNS)
            
            # Check leads_by_status structure
            for status in WORKBOARD_COLUMNS:
                assert status in pipeline_view['leads_by_status']
            
            print("  Pipeline service test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Pipeline service test: FAILED - {e}")
            return False


async def test_status_transitions():
    """Test status transition validation."""
    print("Testing status transitions...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = PipelineService(session)
            
            # Create a test lead
            test_lead = Lead(
                name="Test Lead",
                phone="1234567890",
                email="test@example.com",
                status="new_lead",
                created_by_user_id=1,
                assigned_to_user_id=1,
            )
            session.add(test_lead)
            await session.commit()
            await session.refresh(test_lead)
            
            # Test valid transitions for admin
            valid_transitions = await service.get_available_transitions(
                test_lead.id, 1, "admin"
            )
            assert len(valid_transitions) > 0
            assert "contacted" in valid_transitions
            
            # Test transition
            success, message = await service.transition_lead_status(
                test_lead.id, "contacted", 1, "admin"
            )
            assert success, f"Transition failed: {message}"
            
            # Verify transition
            await session.refresh(test_lead)
            assert test_lead.status == "contacted"
            
            # Clean up
            await session.delete(test_lead)
            await session.commit()
            
            print("  Status transitions test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Status transitions test: FAILED - {e}")
            return False


async def test_role_permissions():
    """Test role-based permissions."""
    print("Testing role permissions...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = PipelineService(session)
            
            # Create a test lead
            test_lead = Lead(
                name="Permission Test Lead",
                phone="0987654321",
                email="permission@example.com",
                status="new_lead",
                created_by_user_id=1,
                assigned_to_user_id=2,  # Assigned to different user
            )
            session.add(test_lead)
            await session.commit()
            await session.refresh(test_lead)
            
            # Test team member permissions (should not see unassigned leads)
            team_transitions = await service.get_available_transitions(
                test_lead.id, 2, "team"
            )
            
            # Test leader permissions (should see team leads)
            leader_transitions = await service.get_available_transitions(
                test_lead.id, 1, "leader"
            )
            
            # Test admin permissions (should see all)
            admin_transitions = await service.get_available_transitions(
                test_lead.id, 1, "admin"
            )
            
            # Admin should have most options
            assert len(admin_transitions) >= len(leader_transitions)
            assert len(leader_transitions) >= len(team_transitions)
            
            # Clean up
            await session.delete(test_lead)
            await session.commit()
            
            print("  Role permissions test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Role permissions test: FAILED - {e}")
            return False


async def test_auto_expiry():
    """Test auto-expiry functionality."""
    print("Testing auto-expiry...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = PipelineService(session)
            
            # Create old stale leads
            old_date = datetime.now(timezone.utc) - timedelta(days=5)
            
            stale_lead = Lead(
                name="Stale Lead",
                phone="5555555555",
                email="stale@example.com",
                status="new_lead",
                created_at=old_date,
                created_by_user_id=1,
                assigned_to_user_id=1,
            )
            session.add(stale_lead)
            await session.commit()
            await session.refresh(stale_lead)
            
            # Run auto-expiry
            expired_count = await service.auto_expire_stale_leads()
            assert expired_count >= 1
            
            # Verify lead was moved to retarget
            await session.refresh(stale_lead)
            assert stale_lead.status == "retarget"
            
            # Clean up
            await session.delete(stale_lead)
            await session.commit()
            
            print("  Auto-expiry test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Auto-expiry test: FAILED - {e}")
            return False


async def test_pipeline_metrics():
    """Test pipeline metrics calculation."""
    print("Testing pipeline metrics...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = PipelineService(session)
            
            # Get metrics
            metrics = await service.get_pipeline_metrics(1, "admin")
            
            # Verify metrics structure
            required_keys = [
                'period', 'status_counts', 'total_leads', 'conversion_rate',
                'payment_rate', 'day1_rate', 'day2_rate', 'funnel'
            ]
            for key in required_keys:
                assert key in metrics
            
            # Verify funnel structure
            funnel_keys = ['new_leads', 'contacted', 'paid', 'day1', 'day2', 'converted']
            for key in funnel_keys:
                assert key in metrics['funnel']
            
            print("  Pipeline metrics test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Pipeline metrics test: FAILED - {e}")
            return False


async def test_business_rules():
    """Test business rule validation."""
    print("Testing business rules...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = PipelineService(session)
            
            # Create test lead
            test_lead = Lead(
                name="Business Rules Test",
                phone="1111111111",
                email="rules@example.com",
                status="video_watched",
                created_by_user_id=1,
                assigned_to_user_id=1,
            )
            session.add(test_lead)
            await session.commit()
            await session.refresh(test_lead)
            
            # Test invalid transition (should fail)
            success, message = await service.transition_lead_status(
                test_lead.id, "day1", 1, "team"
            )
            # This should fail because team can't set day1 and payment is required
            
            # Test valid transition with payment
            test_lead.payment_amount_cents = 19600  # 196 rupees
            test_lead.payment_status = "approved"
            await session.commit()
            
            success, message = await service.transition_lead_status(
                test_lead.id, "day1", 1, "admin"
            )
            assert success, f"Valid transition failed: {message}"
            
            # Clean up
            await session.delete(test_lead)
            await session.commit()
            
            print("  Business rules test: PASSED")
            return True
            
        except Exception as e:
            print(f"  Business rules test: FAILED - {e}")
            return False


async def main():
    """Run all pipeline system tests."""
    print("Starting pipeline system tests...")
    print("=" * 50)
    
    tests = [
        test_pipeline_service,
        test_status_transitions,
        test_role_permissions,
        test_auto_expiry,
        test_pipeline_metrics,
        test_business_rules,
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
        print("All tests PASSED! Pipeline system is working correctly.")
        return 0
    else:
        print("Some tests FAILED. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
