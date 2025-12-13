"""
Simulation Dashboard

Dashboard UI and API endpoints for monitoring and controlling simulation.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
import logging
from datetime import datetime
from typing import Dict, List

from .signal_storage import SignalStorage
from .demo_mode import DemoModeManager
from .emotion_bias import EmotionBiasManager
from .generation_interval import GenerationIntervalManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation Dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the simulation dashboard HTML page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Well-Bot Simulation Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: monospace;
            background-color: #000;
            color: #fff;
            padding: 20px;
            overflow-x: hidden;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 20px;
            color: #0f0;
        }
        
        .demo-mode-section {
            background-color: #111;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .demo-mode-section h2 {
            color: #0ff;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }
        
        .demo-mode-control {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .toggle-switch {
            position: relative;
            width: 60px;
            height: 30px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #333;
            transition: .4s;
            border-radius: 30px;
            border: 1px solid #555;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 22px;
            width: 22px;
            left: 4px;
            bottom: 3px;
            background-color: #fff;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background-color: #0f0;
        }
        
        input:checked + .slider:before {
            transform: translateX(30px);
        }
        
        .status-indicator {
            padding: 5px 12px;
            border: 1px solid #333;
            border-radius: 3px;
            font-weight: bold;
            font-size: 12px;
        }
        
        .status-on {
            background-color: #0f0;
            color: #000;
            border-color: #0f0;
        }
        
        .status-off {
            background-color: #333;
            color: #fff;
            border-color: #555;
        }
        
        .demo-mode-description {
            flex: 1;
            color: #aaa;
            font-size: 0.9em;
        }
        
        .interval-control {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #333;
        }
        
        .interval-control-label {
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 8px;
            display: block;
        }
        
        .interval-input-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .interval-input {
            width: 80px;
            padding: 5px 10px;
            background-color: #222;
            border: 1px solid #555;
            border-radius: 3px;
            color: #fff;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .interval-input:focus {
            outline: none;
            border-color: #0ff;
        }
        
        .interval-unit {
            color: #aaa;
            font-size: 0.85em;
        }
        
        .interval-button {
            padding: 5px 15px;
            background-color: #333;
            border: 1px solid #555;
            border-radius: 3px;
            color: #fff;
            cursor: pointer;
            font-family: monospace;
            font-size: 0.85em;
            transition: all 0.2s;
        }
        
        .interval-button:hover {
            background-color: #444;
            border-color: #0ff;
        }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 60px;
        }
        
        .column {
            background-color: #111;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 15px;
            overflow-y: auto;
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
            min-height: 400px;
        }
        
        .column h2 {
            color: #0ff;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
            position: sticky;
            top: 0;
            background-color: #111;
            z-index: 10;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #333;
            font-size: 0.9em;
        }
        
        .stat-item:last-child {
            border-bottom: none;
        }
        
        .stat-label {
            color: #aaa;
        }
        
        .stat-value {
            color: #fff;
            font-weight: bold;
        }
        
        .signals-list {
            flex: 1;
            overflow-y: auto;
            margin-top: 10px;
            min-height: 0;
        }
        
        .signal-item {
            padding: 10px;
            margin-bottom: 10px;
            border: 1px solid #333;
            border-radius: 3px;
            background-color: #1a1a1a;
            border-left: 3px solid #0ff;
        }
        
        .signal-item .emotion {
            color: #0f0;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .signal-item .confidence {
            color: #ff0;
            font-size: 0.9em;
            margin-bottom: 3px;
        }
        
        .signal-item .timestamp {
            color: #888;
            font-size: 0.85em;
        }
        
        .empty-message {
            color: #666;
            text-align: center;
            padding: 20px;
            font-style: italic;
        }
        
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #111;
            border-top: 1px solid #333;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9em;
        }
        
        .status-indicator-bar {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: #0f0;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .refresh-info {
            color: #666;
            font-size: 0.85em;
        }
        
        .bias-selector {
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        
        .bias-selector-label {
            color: #aaa;
            font-size: 0.85em;
            margin-bottom: 8px;
            display: block;
        }
        
        .bias-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .bias-button {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 2px solid #555;
            background-color: #222;
            color: #fff;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75em;
            font-weight: bold;
            transition: all 0.2s;
            text-transform: uppercase;
        }
        
        .bias-button:hover {
            border-color: #0ff;
            background-color: #333;
        }
        
        .bias-button.selected {
            border-color: #0f0;
            background-color: #0f0;
            color: #000;
        }
        
        .bias-button.none {
            font-size: 0.7em;
        }
    </style>
</head>
<body>
    <h1>Well-Bot Simulation Dashboard</h1>
    
    <div class="demo-mode-section">
        <h2>Demo Mode Control</h2>
        <div class="demo-mode-control">
            <label class="toggle-switch">
                <input type="checkbox" id="demoModeToggle" onchange="toggleDemoMode()">
                <span class="slider"></span>
            </label>
            <span id="demoModeStatus" class="status-indicator status-off">OFF</span>
            <span class="demo-mode-description">
                When enabled, Fusion will use simulation endpoints and signal generator will generate signals.
            </span>
        </div>
        <div class="interval-control">
            <span class="interval-control-label">Generation Interval:</span>
            <div class="interval-input-group">
                <input type="number" id="intervalInput" class="interval-input" min="5" max="300" value="30" 
                       onfocus="intervalInputFocused = true" 
                       onblur="intervalInputFocused = false">
                <span class="interval-unit">seconds</span>
                <button class="interval-button" onclick="setGenerationInterval()">Set</button>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="column">
            <h2>SER Signals</h2>
            <div class="bias-selector">
                <span class="bias-selector-label">Emotion Bias:</span>
                <div class="bias-buttons" id="serBiasButtons">
                    <button class="bias-button none selected" data-emotion="null" onclick="setBias('ser', null)">-</button>
                    <button class="bias-button" data-emotion="Happy" onclick="setBias('ser', 'Happy')">H</button>
                    <button class="bias-button" data-emotion="Sad" onclick="setBias('ser', 'Sad')">S</button>
                    <button class="bias-button" data-emotion="Fear" onclick="setBias('ser', 'Fear')">F</button>
                    <button class="bias-button" data-emotion="Angry" onclick="setBias('ser', 'Angry')">A</button>
                </div>
            </div>
            <div class="stat-item">
                <span class="stat-label">Signal Count:</span>
                <span class="stat-value" id="serCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">File Size:</span>
                <span class="stat-value" id="serSize">0 bytes</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Last Modified:</span>
                <span class="stat-value" id="serModified">-</span>
            </div>
            <div class="signals-list" id="serSignals">
                <div class="empty-message">No signals yet</div>
            </div>
        </div>
        
        <div class="column">
            <h2>FER Signals</h2>
            <div class="bias-selector">
                <span class="bias-selector-label">Emotion Bias:</span>
                <div class="bias-buttons" id="ferBiasButtons">
                    <button class="bias-button none selected" data-emotion="null" onclick="setBias('fer', null)">-</button>
                    <button class="bias-button" data-emotion="Happy" onclick="setBias('fer', 'Happy')">H</button>
                    <button class="bias-button" data-emotion="Sad" onclick="setBias('fer', 'Sad')">S</button>
                    <button class="bias-button" data-emotion="Fear" onclick="setBias('fer', 'Fear')">F</button>
                    <button class="bias-button" data-emotion="Angry" onclick="setBias('fer', 'Angry')">A</button>
                </div>
            </div>
            <div class="stat-item">
                <span class="stat-label">Signal Count:</span>
                <span class="stat-value" id="ferCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">File Size:</span>
                <span class="stat-value" id="ferSize">0 bytes</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Last Modified:</span>
                <span class="stat-value" id="ferModified">-</span>
            </div>
            <div class="signals-list" id="ferSignals">
                <div class="empty-message">No signals yet</div>
            </div>
        </div>
        
        <div class="column">
            <h2>Vitals Signals</h2>
            <div class="bias-selector">
                <span class="bias-selector-label">Emotion Bias:</span>
                <div class="bias-buttons" id="vitalsBiasButtons">
                    <button class="bias-button none selected" data-emotion="null" onclick="setBias('vitals', null)">-</button>
                    <button class="bias-button" data-emotion="Happy" onclick="setBias('vitals', 'Happy')">H</button>
                    <button class="bias-button" data-emotion="Sad" onclick="setBias('vitals', 'Sad')">S</button>
                    <button class="bias-button" data-emotion="Fear" onclick="setBias('vitals', 'Fear')">F</button>
                    <button class="bias-button" data-emotion="Angry" onclick="setBias('vitals', 'Angry')">A</button>
                </div>
            </div>
            <div class="stat-item">
                <span class="stat-label">Signal Count:</span>
                <span class="stat-value" id="vitalsCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">File Size:</span>
                <span class="stat-value" id="vitalsSize">0 bytes</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Last Modified:</span>
                <span class="stat-value" id="vitalsModified">-</span>
            </div>
            <div class="signals-list" id="vitalsSignals">
                <div class="empty-message">No signals yet</div>
            </div>
        </div>
    </div>
    
    <div class="status-bar">
        <div>
            <span class="status-indicator-bar"></span>
            <span>Status: Connected</span>
        </div>
        <div class="refresh-info">
            Auto-refreshing every 2 seconds
        </div>
    </div>
    
    <script>
        let demoModeEnabled = false;
        let emotionBiases = {
            ser: null,
            fer: null,
            vitals: null
        };
        let generationInterval = 30;
        let intervalInputFocused = false;
        
        // Load initial demo mode status
        async function loadDemoModeStatus() {
            try {
                const response = await fetch('/simulation/demo-mode');
                const data = await response.json();
                demoModeEnabled = data.enabled;
                updateDemoModeUI();
            } catch (error) {
                console.error('Error loading demo mode status:', error);
            }
        }
        
        // Load emotion biases
        async function loadEmotionBiases() {
            try {
                const response = await fetch('/simulation/emotion-bias');
                const data = await response.json();
                emotionBiases = {
                    ser: data.ser || null,
                    fer: data.fer || null,
                    vitals: data.vitals || null
                };
                updateBiasButtons();
            } catch (error) {
                console.error('Error loading emotion biases:', error);
            }
        }
        
        // Load generation interval
        async function loadGenerationInterval() {
            try {
                const response = await fetch('/simulation/generation-interval');
                const data = await response.json();
                const newInterval = data.interval || 30;
                
                // Only update input if it hasn't been manually changed and isn't focused
                const input = document.getElementById('intervalInput');
                if (!intervalInputFocused && input.value == generationInterval) {
                    generationInterval = newInterval;
                    input.value = generationInterval;
                } else {
                    // Update the stored value but don't overwrite user input
                    generationInterval = newInterval;
                }
            } catch (error) {
                console.error('Error loading generation interval:', error);
            }
        }
        
        // Set generation interval
        async function setGenerationInterval() {
            const input = document.getElementById('intervalInput');
            const interval = parseInt(input.value);
            
            if (isNaN(interval) || interval < 5 || interval > 300) {
                alert('Interval must be between 5 and 300 seconds');
                input.value = generationInterval;
                return;
            }
            
            try {
                const response = await fetch('/simulation/generation-interval', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        interval: interval
                    })
                });
                
                const data = await response.json();
                generationInterval = data.interval;
                input.value = generationInterval;
                intervalInputFocused = false; // Reset focus flag after successful set
            } catch (error) {
                console.error('Error setting generation interval:', error);
                alert('Failed to set interval. Please try again.');
                input.value = generationInterval;
            }
        }
        
        // Set emotion bias
        async function setBias(modality, emotion) {
            try {
                const response = await fetch('/simulation/emotion-bias', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        modality: modality,
                        emotion: emotion
                    })
                });
                
                const data = await response.json();
                emotionBiases[modality] = data.emotion;
                updateBiasButtons();
            } catch (error) {
                console.error('Error setting emotion bias:', error);
            }
        }
        
        // Update bias button UI
        function updateBiasButtons() {
            ['ser', 'fer', 'vitals'].forEach(modality => {
                const buttons = document.getElementById(modality + 'BiasButtons');
                if (!buttons) return;
                
                const currentBias = emotionBiases[modality];
                const buttonElements = buttons.querySelectorAll('.bias-button');
                
                buttonElements.forEach(button => {
                    const buttonEmotion = button.getAttribute('data-emotion');
                    const isSelected = (buttonEmotion === 'null' && currentBias === null) ||
                                      (buttonEmotion === currentBias);
                    
                    if (isSelected) {
                        button.classList.add('selected');
                    } else {
                        button.classList.remove('selected');
                    }
                });
            });
        }
        
        // Toggle demo mode
        async function toggleDemoMode() {
            const checkbox = document.getElementById('demoModeToggle');
            const newState = checkbox.checked;
            
            try {
                const response = await fetch('/simulation/demo-mode', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ enabled: newState })
                });
                
                const data = await response.json();
                demoModeEnabled = data.enabled;
                updateDemoModeUI();
            } catch (error) {
                console.error('Error toggling demo mode:', error);
                checkbox.checked = !newState; // Revert checkbox
            }
        }
        
        // Update demo mode UI
        function updateDemoModeUI() {
            const checkbox = document.getElementById('demoModeToggle');
            const status = document.getElementById('demoModeStatus');
            
            checkbox.checked = demoModeEnabled;
            if (demoModeEnabled) {
                status.textContent = 'ON';
                status.className = 'status-indicator status-on';
            } else {
                status.textContent = 'OFF';
                status.className = 'status-indicator status-off';
            }
        }
        
        // Format file size
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 bytes';
            const k = 1024;
            const sizes = ['bytes', 'KB', 'MB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }
        
        // Format timestamp
        function formatTimestamp(isoString) {
            if (!isoString) return '-';
            const date = new Date(isoString);
            return date.toLocaleString();
        }
        
        // Update signals display
        function updateSignalsDisplay(modality, data) {
            const countEl = document.getElementById(modality + 'Count');
            const sizeEl = document.getElementById(modality + 'Size');
            const modifiedEl = document.getElementById(modality + 'Modified');
            const signalsEl = document.getElementById(modality + 'Signals');
            
            countEl.textContent = data.count || 0;
            sizeEl.textContent = formatFileSize(data.file_status?.size || 0);
            modifiedEl.textContent = formatTimestamp(data.file_status?.last_modified);
            
            // Update signals list
            if (data.recent_signals && data.recent_signals.length > 0) {
                signalsEl.innerHTML = data.recent_signals.map(signal => `
                    <div class="signal-item">
                        <div class="emotion">${signal.emotion_label} (${(signal.confidence * 100).toFixed(1)}%)</div>
                        <div class="timestamp">${formatTimestamp(signal.timestamp)}</div>
                    </div>
                `).join('');
            } else {
                signalsEl.innerHTML = '<div class="empty-message">No signals yet</div>';
            }
        }
        
        // Load dashboard data
        async function loadDashboardData() {
            try {
                const response = await fetch('/simulation/dashboard/status');
                const data = await response.json();
                
                // Update each modality
                ['ser', 'fer', 'vitals'].forEach(modality => {
                    if (data[modality]) {
                        updateSignalsDisplay(modality, data[modality]);
                    }
                });
            } catch (error) {
                console.error('Error loading dashboard data:', error);
            }
        }
        
        // Initial load
        loadDemoModeStatus();
        loadEmotionBiases();
        loadGenerationInterval();
        loadDashboardData();
        
        // Auto-refresh every 2 seconds
        setInterval(() => {
            loadDemoModeStatus();
            loadEmotionBiases();
            loadGenerationInterval();
            loadDashboardData();
        }, 2000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@router.get("/dashboard/status")
async def dashboard_status():
    """
    Get dashboard status data.
    
    Returns:
        Dictionary with status for each modality (SER, FER, Vitals)
    """
    try:
        storage = SignalStorage.get_instance()
        demo_manager = DemoModeManager.get_instance()
        bias_manager = EmotionBiasManager.get_instance()
        interval_manager = GenerationIntervalManager.get_instance()
        
        result = {
            "demo_mode": demo_manager.get_status(),
            "emotion_biases": {
                "ser": bias_manager.get_bias("ser"),
                "fer": bias_manager.get_bias("fer"),
                "vitals": bias_manager.get_bias("vitals")
            },
            "generation_interval": interval_manager.get_status(),
            "ser": {},
            "fer": {},
            "vitals": {}
        }
        
        # Get data for each modality
        for modality in ["ser", "fer", "vitals"]:
            count = storage.get_signal_count(modality)
            file_status = storage.get_file_status(modality)
            recent_signals = storage.get_all_signals(modality, limit=20)
            
            result[modality] = {
                "count": count,
                "file_status": file_status,
                "recent_signals": [
                    {
                        "emotion_label": signal.emotion_label,
                        "confidence": signal.confidence,
                        "timestamp": signal.timestamp,
                        "user_id": signal.user_id
                    }
                    for signal in recent_signals
                ]
            }
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting dashboard status: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

