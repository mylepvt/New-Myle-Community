#!/usr/bin/env python3
"""
Comprehensive test runner for all systems.
Run this to verify all phases work correctly.
"""

import asyncio
import subprocess
import sys
from pathlib import Path


def run_test_file(test_file: str) -> tuple[int, str]:
    """Run a single test file and return exit code and output."""
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, f"Test {test_file} timed out after 60 seconds"
    except Exception as e:
        return 1, f"Failed to run {test_file}: {str(e)}"


async def main():
    """Run all test suites and generate comprehensive report."""
    print("Starting comprehensive test suite for all phases...")
    print("=" * 60)
    
    # Define all test files
    test_files = [
        ("Phase 1: Training System", "test_training_system.py"),
        ("Phase 2: Lead Pipeline", "test_pipeline_system.py"),
        ("Phase 3: Wallet System", "test_wallet_system.py"),
        ("Phase 4: Analytics System", "test_analytics_system.py"),
        ("Phase 5: Settings System", "test_settings_system.py"),
    ]
    
    results = []
    total_passed = 0
    total_failed = 0
    
    for phase_name, test_file in test_files:
        print(f"\n{'='*20} {phase_name} {'='*20}")
        
        if not Path(test_file).exists():
            print(f"  Test file {test_file} not found - SKIPPED")
            results.append((phase_name, "SKIPPED", "Test file not found"))
            continue
        
        exit_code, output = run_test_file(test_file)
        
        if exit_code == 0:
            print(f"  {phase_name}: PASSED")
            total_passed += 1
            results.append((phase_name, "PASSED", output))
        else:
            print(f"  {phase_name}: FAILED")
            total_failed += 1
            results.append((phase_name, "FAILED", output))
            
            # Show first few lines of error output
            error_lines = output.strip().split('\n')[:10]
            for line in error_lines:
                if line.strip():
                    print(f"    {line}")
            if len(output.strip().split('\n')) > 10:
                print("    ... (truncated)")
    
    # Generate summary report
    print("\n" + "=" * 60)
    print("COMPREHENSIVE TEST RESULTS")
    print("=" * 60)
    
    for phase_name, status, output in results:
        status_icon = "PASSED" if status == "PASSED" else "FAILED" if status == "FAILED" else "SKIPPED"
        print(f"{phase_name}: {status_icon}")
    
    print(f"\nTotal: {len(results)} phases")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Skipped: {len(results) - total_passed - total_failed}")
    
    # Write detailed report to file
    report_content = "# Myle Dashboard Test Report\n\n"
    report_content += f"Generated: {asyncio.get_event_loop().time()}\n\n"
    
    for phase_name, status, output in results:
        report_content += f"## {phase_name}\n\n"
        report_content += f"**Status:** {status}\n\n"
        if status != "SKIPPED":
            report_content += "### Output:\n\n```\n"
            report_content += output
            report_content += "\n```\n\n"
    
    with open("test_report.md", "w") as f:
        f.write(report_content)
    
    print(f"\nDetailed report saved to: test_report.md")
    
    # Overall result
    if total_failed == 0:
        print("\n" + "=" * 60)
        print("ALL SYSTEMS VERIFIED! Ready for deployment.")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print(f"{total_failed} phase(s) failed. Review errors above.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
