#!/usr/bin/env python3
"""
Test Script for Phase 3: API Endpoints

Tests simulation API endpoints using httpx.
Requires SER service to be running on http://localhost:8008
"""

import sys
import os
import asyncio
import httpx
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8008"


async def test_demo_mode_endpoints():
    """Test demo mode GET and POST endpoints."""
    print("=" * 60)
    print("Testing Demo Mode Endpoints...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Get initial status
        print("\n1. Getting demo mode status...")
        response = await client.get(f"{BASE_URL}/simulation/demo-mode")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Initial status: {data}")
        assert "enabled" in data, "Response should contain 'enabled' key"
        
        # Enable demo mode
        print("\n2. Enabling demo mode...")
        response = await client.post(
            f"{BASE_URL}/simulation/demo-mode",
            json={"enabled": True}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Status after enable: {data}")
        assert data["enabled"] == True, "Demo mode should be enabled"
        
        # Disable demo mode
        print("\n3. Disabling demo mode...")
        response = await client.post(
            f"{BASE_URL}/simulation/demo-mode",
            json={"enabled": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Status after disable: {data}")
        assert data["enabled"] == False, "Demo mode should be disabled"
    
    print("\n✓ Demo mode endpoint tests passed!")


async def test_inject_signals():
    """Test signal injection endpoint."""
    print("\n" + "=" * 60)
    print("Testing Signal Injection Endpoint...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Inject SER signals
        print("\n1. Injecting SER signals...")
        now = datetime.now()
        signals = [
            {
                "user_id": "test-user-123",
                "timestamp": (now - timedelta(seconds=i*10)).isoformat(),
                "modality": "speech",
                "emotion_label": ["Happy", "Sad", "Angry"][i % 3],
                "confidence": 0.7 + (i * 0.05)
            }
            for i in range(3)
        ]
        
        response = await client.post(
            f"{BASE_URL}/simulation/inject-signals",
            json={
                "modality": "ser",
                "signals": signals
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Response: {data}")
        assert data["status"] == "success", "Status should be 'success'"
        assert data["signals_injected"] == len(signals), "Should inject all signals"
        
        # Inject FER signals
        print("\n2. Injecting FER signals...")
        fer_signals = [
            {
                "user_id": "test-user-123",
                "timestamp": (now - timedelta(seconds=i*10)).isoformat(),
                "modality": "face",
                "emotion_label": "Happy",
                "confidence": 0.8
            }
            for i in range(2)
        ]
        
        response = await client.post(
            f"{BASE_URL}/simulation/inject-signals",
            json={
                "modality": "fer",
                "signals": fer_signals
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"   ✓ Response: {response.json()}")
    
    print("\n✓ Signal injection endpoint tests passed!")


async def test_predict_endpoints():
    """Test simulation predict endpoints."""
    print("\n" + "=" * 60)
    print("Testing Simulation Predict Endpoints...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        now = datetime.now()
        request_data = {
            "user_id": "test-user-123",
            "snapshot_timestamp": now.isoformat(),
            "window_seconds": 300
        }
        
        # Test SER predict
        print("\n1. Testing SER predict endpoint...")
        response = await client.post(
            f"{BASE_URL}/simulation/ser/predict",
            json=request_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Found {len(data.get('signals', []))} signals")
        assert "signals" in data, "Response should contain 'signals' key"
        
        # Test FER predict
        print("\n2. Testing FER predict endpoint...")
        response = await client.post(
            f"{BASE_URL}/simulation/fer/predict",
            json=request_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Found {len(data.get('signals', []))} signals")
        
        # Test Vitals predict
        print("\n3. Testing Vitals predict endpoint...")
        response = await client.post(
            f"{BASE_URL}/simulation/vitals/predict",
            json=request_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✓ Found {len(data.get('signals', []))} signals")
        
        # Test with clear=false
        print("\n4. Testing with clear=false...")
        response = await client.post(
            f"{BASE_URL}/simulation/ser/predict?clear=false",
            json=request_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("   ✓ Request with clear=false succeeded")
    
    print("\n✓ Predict endpoint tests passed!")


async def main():
    """Run all Phase 3 tests."""
    print("\n" + "=" * 60)
    print("Phase 3: API Endpoints Testing")
    print("=" * 60)
    print("\nNote: SER service must be running on http://localhost:8008")
    print("Start it with: python -m app.main\n")
    
    try:
        # Check if service is running
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(f"{BASE_URL}/health")
    except Exception as e:
        print(f"\n✗ Error: SER service is not running on {BASE_URL}")
        print("  Please start the service first: python -m app.main")
        sys.exit(1)
    
    try:
        await test_demo_mode_endpoints()
        await test_inject_signals()
        await test_predict_endpoints()
        
        print("\n" + "=" * 60)
        print("All Phase 3 tests passed! ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


