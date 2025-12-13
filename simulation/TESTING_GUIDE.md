# Simulation Module Testing Guide

This guide covers testing Phases 1-5 of the simulation module implementation.

## Prerequisites

1. Ensure you're in the `Well-Bot_SER` directory
2. Activate your virtual environment (if using one)
3. Install dependencies: `pip install -r requirements.txt`
4. Ensure `httpx` is installed (for signal generator cloud mode)

## Phase 1: Core Infrastructure Testing

### 1.1 Test SignalStorage

```python
# Test script: test_signal_storage.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.signal_storage import SignalStorage
from app.models import ModelSignal
from datetime import datetime, timedelta

# Get storage instance
storage = SignalStorage.get_instance()

# Create a test signal
test_signal = ModelSignal(
    user_id="test-user-123",
    timestamp=datetime.now().isoformat(),
    modality="speech",
    emotion_label="Happy",
    confidence=0.85
)

# Write signal
print("Writing signal...")
storage.write_signal("ser", test_signal)
print("✓ Signal written")

# Read signals
print("\nReading signals...")
signals = storage.read_signals_in_window(
    "ser",
    "test-user-123",
    datetime.now() - timedelta(minutes=5),
    datetime.now()
)
print(f"✓ Found {len(signals)} signals")

# Get count
count = storage.get_signal_count("ser")
print(f"✓ Signal count: {count}")

# Get file status
status = storage.get_file_status("ser")
print(f"✓ File status: {status}")

# Clear signals
print("\nClearing signals...")
storage.clear_signals("ser")
print("✓ Signals cleared")
```

**Run:**
```bash
cd Well-Bot_SER
python -c "exec(open('simulation/TESTING_GUIDE.md').read())"  # Or create test_signal_storage.py
```

### 1.2 Test DemoModeManager

```python
# Test script: test_demo_mode.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.demo_mode import DemoModeManager

# Get demo mode manager
demo_manager = DemoModeManager.get_instance()

# Check initial state
print(f"Initial demo mode: {demo_manager.is_enabled()}")

# Enable demo mode
print("\nEnabling demo mode...")
demo_manager.set_enabled(True)
print(f"✓ Demo mode enabled: {demo_manager.is_enabled()}")

# Get status
status = demo_manager.get_status()
print(f"✓ Status: {status}")

# Disable demo mode
print("\nDisabling demo mode...")
demo_manager.set_enabled(False)
print(f"✓ Demo mode disabled: {demo_manager.is_enabled()}")
```

## Phase 2: Signal Generator Testing

### 2.1 Test Local Signal Generation

```bash
cd Well-Bot_SER

# Generate signals once for all modalities
python -m simulation.signal_generator --modality all --once --user-id test-user-123

# Generate signals continuously (every 10 seconds) for SER only
python -m simulation.signal_generator --modality ser --interval 10 --user-id test-user-123

# Generate 3 signals per generation
python -m simulation.signal_generator --modality all --once --count 3 --user-id test-user-123
```

**Expected Output:**
- Signals should be written to `data/simulation/SER_signals.jsonl`, `FER_signals.jsonl`, `Vitals_signals.jsonl`
- Check files exist and contain JSON lines

### 2.2 Test Cloud Signal Generation (Requires SER Service Running)

**Terminal 1 - Start SER Service:**
```bash
cd Well-Bot_SER
python -m app.main
```

**Terminal 2 - Generate Signals:**
```bash
cd Well-Bot_SER
python -m simulation.signal_generator --modality all --interval 30 --cloud-url http://localhost:8008 --user-id test-user-123
```

**Expected Behavior:**
- Signals are sent to `/simulation/inject-signals` endpoint
- Check SER service logs for injection confirmation
- Signals appear in JSONL files

### 2.3 Test Demo Mode Integration

**Terminal 1 - Start SER Service:**
```bash
cd Well-Bot_SER
python -m app.main
```

**Terminal 2 - Enable Demo Mode:**
```bash
curl -X POST http://localhost:8008/simulation/demo-mode -H "Content-Type: application/json" -d "{\"enabled\": true}"
```

**Terminal 3 - Start Signal Generator:**
```bash
cd Well-Bot_SER
python -m simulation.signal_generator --modality all --interval 30 --cloud-url http://localhost:8008 --user-id test-user-123
```

**Expected Behavior:**
- Signal generator checks demo mode before generating
- If demo mode is OFF, generator waits
- If demo mode is ON, generator creates signals

**Test Disabling Demo Mode:**
```bash
curl -X POST http://localhost:8008/simulation/demo-mode -H "Content-Type: application/json" -d "{\"enabled\": false}"
```

- Signal generator should stop generating (in continuous mode)

## Phase 3: API Endpoints Testing

### 3.1 Start SER Service

```bash
cd Well-Bot_SER
python -m app.main
```

Service should start on `http://localhost:8008`

### 3.2 Test Demo Mode Endpoints

**Get Demo Mode Status:**
```bash
curl http://localhost:8008/simulation/demo-mode
```

**Expected Response:**
```json
{"enabled": false}
```

**Set Demo Mode:**
```bash
curl -X POST http://localhost:8008/simulation/demo-mode \
  -H "Content-Type: application/json" \
  -d "{\"enabled\": true}"
```

**Expected Response:**
```json
{"enabled": true}
```

### 3.3 Test Signal Injection Endpoint

**Inject Signals:**
```bash
curl -X POST http://localhost:8008/simulation/inject-signals \
  -H "Content-Type: application/json" \
  -d '{
    "modality": "ser",
    "signals": [
      {
        "user_id": "test-user-123",
        "timestamp": "2024-01-15T10:30:00+08:00",
        "modality": "speech",
        "emotion_label": "Happy",
        "confidence": 0.85
      }
    ]
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "modality": "ser",
  "signals_injected": 1
}
```

### 3.4 Test Simulation Predict Endpoints

**First, inject some signals (see 3.3)**

**Test SER Predict:**
```bash
curl -X POST http://localhost:8008/simulation/ser/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "snapshot_timestamp": "2024-01-15T10:35:00+08:00",
    "window_seconds": 300
  }'
```

**Expected Response:**
```json
{
  "signals": [
    {
      "user_id": "test-user-123",
      "timestamp": "2024-01-15T10:30:00+08:00",
      "modality": "speech",
      "emotion_label": "Happy",
      "confidence": 0.85
    }
  ]
}
```

**Test FER Predict:**
```bash
curl -X POST http://localhost:8008/simulation/fer/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "snapshot_timestamp": "2024-01-15T10:35:00+08:00",
    "window_seconds": 300
  }'
```

**Test Vitals Predict:**
```bash
curl -X POST http://localhost:8008/simulation/vitals/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "snapshot_timestamp": "2024-01-15T10:35:00+08:00",
    "window_seconds": 300
  }'
```

**Test with clear=false:**
```bash
curl -X POST "http://localhost:8008/simulation/ser/predict?clear=false" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "snapshot_timestamp": "2024-01-15T10:35:00+08:00",
    "window_seconds": 300
  }'
```

## Phase 4: Dashboard Testing

### 4.1 Access Dashboard

**Start SER Service:**
```bash
cd Well-Bot_SER
python -m app.main
```

**Open Browser:**
Navigate to: `http://localhost:8008/simulation/dashboard`

**Expected:**
- Dashboard loads with demo mode toggle
- Shows signal counts for SER, FER, Vitals (all 0 initially)
- Auto-refreshes every 2 seconds

### 4.2 Test Demo Mode Toggle

1. Click the toggle switch
2. Status should change from "OFF" (red) to "ON" (green)
3. Check API response:
   ```bash
   curl http://localhost:8008/simulation/demo-mode
   ```
   Should return `{"enabled": true}`

### 4.3 Test Dashboard Status API

```bash
curl http://localhost:8008/simulation/dashboard/status
```

**Expected Response:**
```json
{
  "demo_mode": {"enabled": false},
  "ser": {
    "count": 0,
    "file_status": {
      "exists": true,
      "size": 0,
      "last_modified": null
    },
    "recent_signals": []
  },
  "fer": {...},
  "vitals": {...}
}
```

### 4.4 Test with Signals

1. Generate some signals (see Phase 2)
2. Refresh dashboard
3. Should see:
   - Signal counts > 0
   - File sizes > 0
   - Recent signals displayed
   - Last modified timestamps

## Phase 5: Integration Testing

### 5.1 Verify Routes are Accessible

**Check Root Endpoint:**
```bash
curl http://localhost:8008/
```

**Expected Response:**
```json
{
  "message": "Well-Bot SER API is running",
  "status": "healthy",
  "version": "2.0.0",
  "dashboards": {
    "ser": "/ser/dashboard",
    "simulation": "/simulation/dashboard"
  }
}
```

### 5.2 Full Flow Test

**Step 1: Start SER Service**
```bash
cd Well-Bot_SER
python -m app.main
```

**Step 2: Enable Demo Mode**
```bash
curl -X POST http://localhost:8008/simulation/demo-mode \
  -H "Content-Type: application/json" \
  -d "{\"enabled\": true}"
```

**Step 3: Generate Signals**
```bash
cd Well-Bot_SER
python -m simulation.signal_generator --modality all --once --cloud-url http://localhost:8008 --user-id test-user-123
```

**Step 4: Check Dashboard**
- Open `http://localhost:8008/simulation/dashboard`
- Should see signals for all modalities

**Step 5: Read Signals via API**
```bash
curl -X POST http://localhost:8008/simulation/ser/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "snapshot_timestamp": "2024-01-15T10:35:00+08:00",
    "window_seconds": 300
  }'
```

**Step 6: Verify Signals Cleared**
- Check dashboard again
- Signal counts should be 0 (if clear=true)

## Troubleshooting

### Import Errors
If you get import errors, ensure you're running from `Well-Bot_SER` directory:
```bash
cd Well-Bot_SER
python -m simulation.signal_generator --help
```

### Port Already in Use
If port 8008 is in use, change it:
```bash
export PORT=8009
python -m app.main
```

### JSONL Files Not Created
Check that `data/simulation/` directory exists:
```bash
mkdir -p data/simulation
```

### Demo Mode Not Persisting
Demo mode is in-memory and resets on service restart. This is expected behavior.

## Next Steps

After testing Phases 1-5, proceed to Phase 6: Update Fusion Service to use simulation endpoints when demo mode is enabled.


