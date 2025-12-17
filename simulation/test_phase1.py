#!/usr/bin/env python3
"""
Test Script for Phase 1: Core Infrastructure

Tests DemoModeManager and other simulation components.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.demo_mode import DemoModeManager


def test_demo_mode():
    """Test DemoModeManager class."""
    print("\n" + "=" * 60)
    print("Testing DemoModeManager...")
    print("=" * 60)
    
    demo_manager = DemoModeManager.get_instance()
    
    # Check initial state
    print("\n1. Checking initial state...")
    initial_state = demo_manager.is_enabled()
    print(f"   ✓ Initial demo mode: {initial_state}")
    
    # Enable demo mode
    print("\n2. Enabling demo mode...")
    demo_manager.set_enabled(True)
    assert demo_manager.is_enabled() == True, "Demo mode should be enabled"
    print("   ✓ Demo mode enabled")
    
    # Get status
    print("\n3. Getting status...")
    status = demo_manager.get_status()
    print(f"   ✓ Status: {status}")
    assert status["enabled"] == True, "Status should show enabled=True"
    
    # Disable demo mode
    print("\n4. Disabling demo mode...")
    demo_manager.set_enabled(False)
    assert demo_manager.is_enabled() == False, "Demo mode should be disabled"
    print("   ✓ Demo mode disabled")
    
    print("\n✓ DemoModeManager tests passed!")


if __name__ == "__main__":
    try:
        test_demo_mode()
        print("\n" + "=" * 60)
        print("All Phase 1 tests passed! ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


