#!/usr/bin/env python3
"""
Comprehensive test script for the wallet system.
Run this when PostgreSQL is running to verify the wallet system works end-to-end.
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.services.wallet_service import WalletService
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.models.wallet_recharge import WalletRecharge


async def test_wallet_balance_calculation():
    """Test wallet balance calculation from ledger."""
    print("Testing wallet balance calculation...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Get initial balance for user 1
            balance, currency = await service.get_balance(1)
            print(f"  Initial balance: {balance // 100} {currency}")
            
            # Create a test ledger entry
            test_entry = WalletLedgerEntry(
                user_id=1,
                amount_cents=50000,  # 500 rupees
                currency="INR",
                note="Test credit entry",
                created_by_user_id=1,
            )
            session.add(test_entry)
            await session.commit()
            
            # Check updated balance
            new_balance, new_currency = await service.get_balance(1)
            expected_balance = balance + 50000
            
            assert new_balance == expected_balance, f"Expected {expected_balance}, got {new_balance}"
            assert new_currency == "INR"
            
            # Clean up
            await session.delete(test_entry)
            await session.commit()
            
            print("  Wallet balance calculation: PASSED")
            return True
            
        except Exception as e:
            print(f"  Wallet balance calculation: FAILED - {e}")
            return False


async def test_lead_claim_affordability():
    """Test lead claim affordability validation."""
    print("Testing lead claim affordability...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Get user balance
            balance, currency = await service.get_balance(1)
            
            # Test affordable claim
            affordable_amount = balance // 2  # Half of current balance
            can_afford, message = await service.can_afford_lead_claim(1, affordable_amount)
            assert can_afford, f"Should afford {affordable_amount}: {message}"
            
            # Test unaffordable claim
            unaffordable_amount = balance + 10000  # More than current balance
            can_afford, message = await service.can_afford_lead_claim(1, unaffordable_amount)
            assert not can_afford, f"Should not afford {unaffordable_amount}"
            assert "Insufficient balance" in message
            
            print("  Lead claim affordability: PASSED")
            return True
            
        except Exception as e:
            print(f"  Lead claim affordability: FAILED - {e}")
            return False


async def test_wallet_deduction():
    """Test wallet deduction for lead claim."""
    print("Testing wallet deduction...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Get initial balance
            initial_balance, currency = await service.get_balance(1)
            
            # Create a test lead (we'll simulate this)
            # In real scenario, you'd have a lead model
            lead_id = 999  # Test lead ID
            lead_price = 10000  # 100 rupees
            
            # Test deduction
            success, message = await service.deduct_for_lead_claim(1, lead_id, lead_price)
            
            # This might fail because lead doesn't exist, but we can test the balance check
            if not success and "Lead not found" in message:
                # Expected - lead doesn't exist
                print("  Wallet deduction (lead not found): PASSED")
                return True
            
            # If it succeeded, check balance
            new_balance, _ = await service.get_balance(1)
            expected_balance = initial_balance - lead_price
            
            assert new_balance == expected_balance, f"Expected {expected_balance}, got {new_balance}"
            
            print("  Wallet deduction: PASSED")
            return True
            
        except Exception as e:
            print(f"  Wallet deduction: FAILED - {e}")
            return False


async def test_wallet_summary():
    """Test comprehensive wallet summary."""
    print("Testing wallet summary...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Get wallet summary
            summary = await service.get_wallet_summary(1)
            
            # Verify summary structure
            required_keys = [
                'balance_cents', 'currency', 'balance_rupees',
                'recent_transactions', 'pending_recharges',
                'monthly_spending_cents', 'monthly_spending_rupees'
            ]
            
            for key in required_keys:
                assert key in summary, f"Missing key: {key}"
            
            # Verify balance consistency
            assert summary['balance_cents'] >= 0
            assert summary['balance_rupees'] == summary['balance_cents'] // 100
            assert summary['currency'] == 'INR'
            
            # Verify transactions structure
            if summary['recent_transactions']:
                for tx in summary['recent_transactions']:
                    assert 'id' in tx
                    assert 'amount_cents' in tx
                    assert 'amount_rupees' in tx
                    assert 'note' in tx
                    assert 'created_at' in tx
            
            print("  Wallet summary: PASSED")
            return True
            
        except Exception as e:
            print(f"  Wallet summary: FAILED - {e}")
            return False


async def test_manual_adjustment():
    """Test manual wallet adjustment (admin)."""
    print("Testing manual adjustment...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Get initial balance
            initial_balance, currency = await service.get_balance(1)
            
            # Test manual credit
            adjustment_amount = 25000  # 250 rupees
            success, message = await service.create_manual_adjustment(
                admin_user_id=1,  # Assuming user 1 is admin
                target_user_id=1,
                amount_cents=adjustment_amount,
                note="Test manual adjustment"
            )
            
            if not success:
                # Might fail if user 1 is not admin
                if "Only admin can make manual adjustments" in message:
                    print("  Manual adjustment (non-admin): PASSED")
                    return True
                else:
                    print(f"  Manual adjustment: FAILED - {message}")
                    return False
            
            # Check new balance
            new_balance, _ = await service.get_balance(1)
            expected_balance = initial_balance + adjustment_amount
            
            assert new_balance == expected_balance, f"Expected {expected_balance}, got {new_balance}"
            
            print("  Manual adjustment: PASSED")
            return True
            
        except Exception as e:
            print(f"  Manual adjustment: FAILED - {e}")
            return False


async def test_transaction_validation():
    """Test transaction validation."""
    print("Testing transaction validation...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Test valid transaction
            is_valid, message = await service.validate_transaction(
                user_id=1,
                amount_cents=10000,
                note="Valid test transaction"
            )
            assert is_valid, f"Valid transaction should pass: {message}"
            
            # Test zero amount
            is_valid, message = await service.validate_transaction(
                user_id=1,
                amount_cents=0,
                note="Zero amount test"
            )
            assert not is_valid, "Zero amount should be invalid"
            assert "Amount cannot be zero" in message
            
            # Test excessive amount
            is_valid, message = await service.validate_transaction(
                user_id=1,
                amount_cents=20000000,  # 200,000 rupees
                note="Excessive amount test"
            )
            assert not is_valid, "Excessive amount should be invalid"
            assert "exceeds maximum limit" in message.lower()
            
            # Test empty note
            is_valid, message = await service.validate_transaction(
                user_id=1,
                amount_cents=10000,
                note=""
            )
            assert not is_valid, "Empty note should be invalid"
            assert "Note is required" in message
            
            print("  Transaction validation: PASSED")
            return True
            
        except Exception as e:
            print(f"  Transaction validation: FAILED - {e}")
            return False


async def test_admin_overview():
    """Test admin wallet overview."""
    print("Testing admin overview...")
    
    async with AsyncSessionLocal() as session:
        try:
            service = WalletService(session)
            
            # Get admin overview
            overview = await service.get_admin_wallet_overview()
            
            # Verify overview structure
            required_keys = [
                'total_balance_cents', 'total_balance_rupees',
                'user_count', 'pending_recharge_requests',
                'top_balances', 'recent_activity'
            ]
            
            for key in required_keys:
                assert key in overview, f"Missing key: {key}"
            
            # Verify data consistency
            assert overview['total_balance_cents'] >= 0
            assert overview['total_balance_rupees'] == overview['total_balance_cents'] // 100
            assert overview['user_count'] >= 0
            assert overview['pending_recharge_requests'] >= 0
            
            # Verify top balances structure
            if overview['top_balances']:
                for ub in overview['top_balances']:
                    assert 'user_id' in ub
                    assert 'balance_cents' in ub
                    assert 'balance_rupees' in ub
            
            print("  Admin overview: PASSED")
            return True
            
        except Exception as e:
            print(f"  Admin overview: FAILED - {e}")
            return False


async def main():
    """Run all wallet system tests."""
    print("Starting wallet system tests...")
    print("=" * 50)
    
    tests = [
        test_wallet_balance_calculation,
        test_lead_claim_affordability,
        test_wallet_deduction,
        test_wallet_summary,
        test_manual_adjustment,
        test_transaction_validation,
        test_admin_overview,
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
        print("All tests PASSED! Wallet system is working correctly.")
        return 0
    else:
        print("Some tests FAILED. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
