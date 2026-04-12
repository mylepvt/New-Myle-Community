#!/usr/bin/env python3
"""
Comprehensive test script for the analytics system.
Run this when PostgreSQL is running to verify the analytics system works end-to-end.
"""

import asyncio
import sys
from datetime import date, datetime, timedelta

from app.services.analytics_service import AnalyticsService
from app.db.session import AsyncSessionLocal
from app.models.daily_report import DailyReport
from app.models.daily_score import DailyScore
from app.models.lead import Lead
from app.models.user import User


async def test_team_performance_summary():
    """Test team performance summary calculation."""
    print("Testing team performance summary...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            # Test with user_id 1 (assuming leader/admin)
            performance = await service.get_team_performance_summary(1, 30)
            
            # Verify structure
            required_keys = ['period', 'team_size', 'reports', 'leads', 'scores']
            for key in required_keys:
                assert key in performance, f"Missing key: {key}"
            
            # Verify reports structure
            reports_keys = ['total_reports', 'total_calls', 'calls_picked', 'enrollments', 'payments', 'pickup_rate']
            for key in reports_keys:
                assert key in performance['reports'], f"Missing reports key: {key}"
            
            # Verify leads structure
            leads_keys = ['total_leads', 'converted_leads', 'paid_leads', 'conversion_rate', 'payment_rate']
            for key in leads_keys:
                assert key in performance['leads'], f"Missing leads key: {key}"
            
            # Verify scores structure
            scores_keys = ['total_points', 'avg_daily_points', 'days_with_reports']
            for key in scores_keys:
                assert key in performance['scores'], f"Missing scores key: {key}"
            
            # Verify data types
            assert isinstance(performance['team_size'], int)
            assert isinstance(performance['reports']['pickup_rate'], (int, float))
            assert isinstance(performance['leads']['conversion_rate'], (int, float))
            assert isinstance(performance['leads']['payment_rate'], (int, float))
            
            print("  Team performance summary: PASSED")
            return True
            
        except Exception as e:
            print(f"  Team performance summary: FAILED - {e}")
            return False


async def test_individual_performance():
    """Test individual performance calculation."""
    print("Testing individual performance...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            # Test with user_id 1
            performance = await service.get_individual_performance(1, 30)
            
            # Verify structure
            required_keys = ['period', 'reports', 'leads', 'scores', 'daily_trends']
            for key in required_keys:
                assert key in performance, f"Missing key: {key}"
            
            # Verify daily trends
            assert isinstance(performance['daily_trends'], list)
            if performance['daily_trends']:
                trend = performance['daily_trends'][0]
                trend_keys = ['date', 'calls', 'enrollments', 'payments', 'points']
                for key in trend_keys:
                    assert key in trend, f"Missing trend key: {key}"
            
            print("  Individual performance: PASSED")
            return True
            
        except Exception as e:
            print(f"  Individual performance: FAILED - {e}")
            return False


async def test_leaderboard():
    """Test leaderboard calculation."""
    print("Testing leaderboard...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            # Get leaderboard
            leaderboard = await service.get_leaderboard(30)
            
            # Verify structure
            assert isinstance(leaderboard, list)
            
            if leaderboard:
                entry = leaderboard[0]
                entry_keys = ['rank', 'user_id', 'username', 'total_points', 'days_with_reports', 'avg_daily_points', 'total_leads', 'converted_leads']
                for key in entry_keys:
                    assert key in entry, f"Missing leaderboard key: {key}"
                
                # Verify ranking
                for i, entry in enumerate(leaderboard):
                    assert entry['rank'] == i + 1, f"Incorrect rank at position {i}"
                
                # Verify sorting by points
                for i in range(len(leaderboard) - 1):
                    assert leaderboard[i]['total_points'] >= leaderboard[i + 1]['total_points'], "Leaderboard not sorted correctly"
            
            print("  Leaderboard: PASSED")
            return True
            
        except Exception as e:
            print(f"  Leaderboard: FAILED - {e}")
            return False


async def test_system_overview():
    """Test system overview calculation."""
    print("Testing system overview...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            # Get system overview
            overview = await service.get_system_overview(30)
            
            # Verify structure
            required_keys = ['period', 'users', 'reports', 'leads', 'wallet']
            for key in required_keys:
                assert key in overview, f"Missing key: {key}"
            
            # Verify user metrics
            user_keys = ['active_users', 'total_reports']
            for key in user_keys:
                assert key in overview['users'], f"Missing user key: {key}"
            
            # Verify report metrics
            report_keys = ['total_reports', 'total_calls', 'total_enrollments', 'total_payments', 'avg_calls_per_user']
            for key in report_keys:
                assert key in overview['reports'], f"Missing report key: {key}"
            
            # Verify lead metrics
            lead_keys = ['total_leads', 'converted_leads', 'paid_leads', 'conversion_rate']
            for key in lead_keys:
                assert key in overview['leads'], f"Missing lead key: {key}"
            
            # Verify wallet metrics
            wallet_keys = ['active_wallets', 'total_credits', 'total_debits', 'net_volume']
            for key in wallet_keys:
                assert key in overview['wallet'], f"Missing wallet key: {key}"
            
            print("  System overview: PASSED")
            return True
            
        except Exception as e:
            print(f"  System overview: FAILED - {e}")
            return False


async def test_daily_trends():
    """Test daily trends calculation."""
    print("Testing daily trends...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            # Test individual trends
            individual_trends = await service.get_daily_report_trends(1, 30)
            
            # Verify structure
            assert isinstance(individual_trends, list)
            
            if individual_trends:
                trend = individual_trends[0]
                trend_keys = ['date', 'reports_count', 'total_calls', 'total_enrollments', 'total_payments', 'avg_calls_per_report']
                for key in trend_keys:
                    assert key in trend, f"Missing trend key: {key}"
                
                # Verify date format
                assert isinstance(trend['date'], str)
                assert len(trend['date']) == 10  # YYYY-MM-DD format
            
            # Test team trends (None for team-wide)
            team_trends = await service.get_daily_report_trends(None, 30)
            assert isinstance(team_trends, list)
            
            print("  Daily trends: PASSED")
            return True
            
        except Exception as e:
            print(f"  Daily trends: FAILED - {e}")
            return False


async def test_data_consistency():
    """Test data consistency across different analytics."""
    print("Testing data consistency...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            # Get individual performance
            individual = await service.get_individual_performance(1, 30)
            
            # Get leaderboard and find the same user
            leaderboard = await service.get_leaderboard(30)
            user_entry = next((entry for entry in leaderboard if entry['user_id'] == 1), None)
            
            if user_entry and individual['scores']['total_points'] > 0:
                # Verify points match
                assert individual['scores']['total_points'] == user_entry['total_points'], "Points mismatch between individual and leaderboard"
                
                # Verify leads match
                assert individual['leads']['total_leads'] == user_entry['total_leads'], "Leads mismatch between individual and leaderboard"
                
                # Verify converted leads match
                assert individual['leads']['converted_leads'] == user_entry['converted_leads'], "Converted leads mismatch"
            
            print("  Data consistency: PASSED")
            return True
            
        except Exception as e:
            print(f"  Data consistency: FAILED - {e}")
            return False


async def test_period_variations():
    """Test analytics with different time periods."""
    print("Testing period variations...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = AnalyticsService(session)
            
            periods = [7, 30, 90]
            
            for days in periods:
                # Test team performance
                team_perf = await service.get_team_performance_summary(1, days)
                assert team_perf['period'] == f"{days} days"
                
                # Test individual performance
                individual_perf = await service.get_individual_performance(1, days)
                assert individual_perf['period'] == f"{days} days"
                
                # Test system overview
                system_overview = await service.get_system_overview(days)
                assert system_overview['period'] == f"{days} days"
                
                # Test leaderboard
                leaderboard = await service.get_leaderboard(days)
                assert leaderboard[0]['period'] == f"{days} days" if leaderboard else True
            
            print("  Period variations: PASSED")
            return True
            
        except Exception as e:
            print(f"  Period variations: FAILED - {e}")
            return False


async def main():
    """Run all analytics system tests."""
    print("Starting analytics system tests...")
    print("=" * 50)
    
    tests = [
        test_team_performance_summary,
        test_individual_performance,
        test_leaderboard,
        test_system_overview,
        test_daily_trends,
        test_data_consistency,
        test_period_variations,
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
        print("All tests PASSED! Analytics system is working correctly.")
        return 0
    else:
        print("Some tests FAILED. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
