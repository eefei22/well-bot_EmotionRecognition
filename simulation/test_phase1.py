#!/usr/bin/env python3
"""
Test Script for Phase 1: Core Infrastructure

Tests SignalStorage and DemoModeManager.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.signal_storage import SignalStorage
from simulation.demo_mode import DemoModeManager
from app.models import ModelSignal


def test_signal_storage():
    """Test SignalStorage class."""
    print("=" * 60)
    print("Testing SignalStorage...")
    print("=" * 60)
    
    storage = SignalStorage.get_instance()
    
    # Create test signals
    now = datetime.now()
    test_signals = [
        ModelSignal(
            user_id="test-user-123",
            timestamp=(now - timedelta(seconds=i*10)).isoformat(),
            modality="speech",
            emotion_label=["Happy", "Sad", "Angry"][i % 3],
            confidence=0.7 + (i * 0.05)
        )
        for i in range(3)
    ]
    
    # Write signals
    print("\n1. Writing signals...")
    for signal in test_signals:
        storage.write_signal("ser", signal)
    print(f"   ✓ Wrote {len(test_signals)} signals")
    
    # Get count
    print("\n2. Getting signal count...")
    count = storage.get_signal_count("ser")
    print(f"   ✓ Signal count: {count}")
    assert count == len(test_signals), f"Expected {len(test_signals)}, got {count}"
    
    # Read signals in window
    print("\n3. Reading signals in window...")
    signals = storage.read_signals_in_window(
        "ser",
        "test-user-123",
        now - timedelta(minutes=5),
        now
    )
    print(f"   ✓ Found {len(signals)} signals")
    assert len(signals) == len(test_signals), f"Expected {len(test_signals)}, got {len(signals)}"
    
    # Get all signals
    print("\n4. Getting all signals...")
    all_signals = storage.get_all_signals("ser", limit=10)
    print(f"   ✓ Retrieved {len(all_signals)} signals")
    
    # Get file status
    print("\n5. Getting file status...")
    status = storage.get_file_status("ser")
    print(f"   ✓ File exists: {status['exists']}")
    print(f"   ✓ File size: {status['size']} bytes")
    
    # Clear signals
    print("\n6. Clearing signals...")
    storage.clear_signals("ser")
    count_after = storage.get_signal_count("ser")
    print(f"   ✓ Signals cleared (count: {count_after})")
    assert count_after == 0, f"Expected 0, got {count_after}"
    
    print("\n✓ SignalStorage tests passed!")


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
        test_signal_storage()
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

