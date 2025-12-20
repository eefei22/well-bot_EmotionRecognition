"""
Dashboard API endpoints for monitoring queue, processing, and results.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List, Dict, Optional
from datetime import datetime
import logging

from app.queue_manager import QueueManager
from app.database import get_malaysia_timezone
from app.ser_result_logger import read_aggregated_results
from app.config import settings
from app.aggregation_interval import AggregationIntervalManager
from datetime import timedelta
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ser", tags=["SER Dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Well-Bot SER Dashboard</title>
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
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 20px;
            height: calc(100vh - 100px);
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
            min-height: 0;
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
        
        .queue-list, .processing-list, .results-list, .aggregated-list {
            list-style: none;
            flex: 1;
            overflow-y: auto;
            min-height: 0;
        }
        
        .queue-item, .processing-item, .result-item, .aggregated-item {
            padding: 10px;
            margin-bottom: 10px;
            border: 1px solid #333;
            border-radius: 3px;
            background-color: #1a1a1a;
        }
        
        .queue-item {
            border-left: 3px solid #ff0;
        }
        
        .processing-item {
            border-left: 3px solid #0f0;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .result-item {
            border-left: 3px solid #0ff;
        }
        
        .aggregated-item {
            border-left: 3px solid #f0f;
        }
        
        .item-header {
            font-weight: bold;
            color: #0ff;
            margin-bottom: 5px;
        }
        
        .item-detail {
            font-size: 0.9em;
            color: #aaa;
            margin: 3px 0;
        }
        
        .emotion {
            color: #0f0;
            font-weight: bold;
        }
        
        .confidence {
            color: #ff0;
        }
        
        .timestamp {
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
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        
        .status-online {
            background-color: #0f0;
        }
        
        .status-offline {
            background-color: #f00;
        }
    </style>
</head>
<body>
    <h1>Well-Bot SER Dashboard</h1>
    
    <div class="container">
        <!-- Left Column -->
        <div class="column">
            <h2>Queue (Waiting)</h2>
            <ul class="queue-list" id="queueList">
                <li class="empty-message">Loading...</li>
            </ul>
        </div>
        
        <!-- Right Column Top -->
        <div class="column">
            <h2>Results Log</h2>
            <ul class="results-list" id="resultsList">
                <li class="empty-message">No results yet</li>
            </ul>
        </div>
        
        <!-- Left Column Bottom -->
        <div class="column">
            <h2>Processing (Active)</h2>
            <ul class="processing-list" id="processingList">
                <li class="empty-message">No active processing</li>
            </ul>
        </div>
        
        <!-- Right Column Bottom -->
        <div class="column">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h2 style="margin: 0;">Aggregated Results</h2>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label style="color: #888; font-size: 12px;">Aggregation Interval:</label>
                    <input type="number" id="aggregationIntervalInput" min="60" max="3600" style="width: 80px; padding: 4px; background: #1a1a1a; border: 1px solid #444; color: #0f0; font-family: monospace; font-size: 12px;" />
                    <span style="color: #888; font-size: 12px;">seconds</span>
                    <button onclick="setAggregationInterval()" style="padding: 4px 12px; background: #333; border: 1px solid #555; color: #0f0; cursor: pointer; font-family: monospace; font-size: 12px;">Set</button>
                </div>
            </div>
            <ul class="aggregated-list" id="aggregatedList">
                <li class="empty-message">No aggregated results yet</li>
            </ul>
        </div>
    </div>
    
    <div class="status-bar">
        <div>
            <span class="status-indicator status-online" id="statusIndicator"></span>
            <span>Status: <span id="statusText">Connected</span></span>
        </div>
        <div>
            Queue Size: <span id="queueSize">0</span> | 
            Last Update: <span id="lastUpdate">--</span>
        </div>
    </div>
    
    <script>
        let resultsHistory = [];
        let aggregatedHistory = [];
        const MAX_RESULTS_DISPLAY = 100;
        const MAX_AGGREGATED_DISPLAY = 100;
        
        function formatTimestamp(timestamp) {
            if (!timestamp) return '--';
            const date = new Date(timestamp);
            return date.toLocaleString();
        }
        
        function formatTimeWindow(windowStart, windowEnd) {
            if (!windowStart || !windowEnd) return '--';
            const start = new Date(windowStart);
            const end = new Date(windowEnd);
            return `${start.toLocaleTimeString()} - ${end.toLocaleTimeString()}`;
        }
        
        function updateQueue(queueItems) {
            const list = document.getElementById('queueList');
            
            if (!queueItems || queueItems.length === 0) {
                list.innerHTML = '<li class="empty-message">Queue is empty</li>';
                return;
            }
            
            list.innerHTML = queueItems.map(item => `
                <li class="queue-item">
                    <div class="item-header">User: ${item.user_id.substring(0, 8)}...</div>
                    <div class="item-detail timestamp">Queued: ${formatTimestamp(item.timestamp)}</div>
                    <div class="item-detail">File: ${item.filename || 'N/A'}</div>
                </li>
            `).join('');
        }
        
        function updateProcessing(processingItems) {
            const list = document.getElementById('processingList');
            
            if (!processingItems || processingItems.length === 0) {
                list.innerHTML = '<li class="empty-message">No active processing</li>';
                return;
            }
            
            list.innerHTML = processingItems.map(item => `
                <li class="processing-item">
                    <div class="item-header">User: ${item.user_id.substring(0, 8)}...</div>
                    <div class="item-detail timestamp">Started: ${formatTimestamp(item.started_at)}</div>
                    ${item.result ? `
                        <div class="item-detail">
                            <span class="emotion">Emotion: ${item.result.emotion}</span>
                        </div>
                        <div class="item-detail">
                            <span class="confidence">Confidence: ${(item.result.emotion_confidence * 100).toFixed(1)}%</span>
                        </div>
                        ${item.result.sentiment ? `
                            <div class="item-detail">Sentiment: ${item.result.sentiment}</div>
                        ` : ''}
                    ` : '<div class="item-detail">Processing...</div>'}
                </li>
            `).join('');
        }
        
        function updateResults(results) {
            const list = document.getElementById('resultsList');
            
            // Add new results to history
            if (results && results.length > 0) {
                results.forEach(result => {
                    // Check if result already exists in history
                    const exists = resultsHistory.find(r => 
                        r.user_id === result.user_id && 
                        r.timestamp === result.timestamp
                    );
                    if (!exists) {
                        resultsHistory.unshift(result);
                    }
                });
                
                // Keep only last MAX_RESULTS_DISPLAY results
                if (resultsHistory.length > MAX_RESULTS_DISPLAY) {
                    resultsHistory = resultsHistory.slice(0, MAX_RESULTS_DISPLAY);
                }
            }
            
            if (resultsHistory.length === 0) {
                list.innerHTML = '<li class="empty-message">No results yet</li>';
                return;
            }
            
            list.innerHTML = resultsHistory.map(result => `
                <li class="result-item">
                    <div class="item-header">User: ${result.user_id.substring(0, 8)}...</div>
                    <div class="item-detail timestamp">${formatTimestamp(result.timestamp)}</div>
                    <div class="item-detail">
                        <span class="emotion">${result.emotion}</span>
                        <span class="confidence">(${(result.emotion_confidence * 100).toFixed(1)}%)</span>
                    </div>
                    ${result.sentiment ? `
                        <div class="item-detail">Sentiment: ${result.sentiment}</div>
                    ` : ''}
                    ${result.transcript ? `
                        <div class="item-detail" style="color: #888; font-size: 0.85em; margin-top: 5px;">
                            "${result.transcript.substring(0, 50)}${result.transcript.length > 50 ? '...' : ''}"
                        </div>
                    ` : ''}
                </li>
            `).join('');
        }
        
        function updateAggregated(aggregatedResults) {
            const list = document.getElementById('aggregatedList');
            
            // Add new aggregated results to history
            if (aggregatedResults && aggregatedResults.length > 0) {
                aggregatedResults.forEach(result => {
                    // Check if result already exists in history
                    const exists = aggregatedHistory.find(r => 
                        r.user_id === result.user_id && 
                        r.session_id === result.session_id &&
                        r.timestamp === result.timestamp
                    );
                    if (!exists) {
                        aggregatedHistory.unshift(result);
                    }
                });
                
                // Keep only last MAX_AGGREGATED_DISPLAY results
                if (aggregatedHistory.length > MAX_AGGREGATED_DISPLAY) {
                    aggregatedHistory = aggregatedHistory.slice(0, MAX_AGGREGATED_DISPLAY);
                }
            }
            
            if (aggregatedHistory.length === 0) {
                list.innerHTML = '<li class="empty-message">No aggregated results yet</li>';
                return;
            }
            
            list.innerHTML = aggregatedHistory.map(result => {
                const agg = result.aggregated_result || {};
                return `
                    <li class="aggregated-item">
                        <div class="item-header">User: ${result.user_id.substring(0, 8)}...</div>
                        <div class="item-detail timestamp">${formatTimestamp(result.timestamp)}</div>
                        <div class="item-detail" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>
                                <span class="emotion">${agg.emotion || 'N/A'}</span>
                                <span class="confidence">(${((agg.emotion_confidence || 0) * 100).toFixed(1)}%)</span>
                            </div>
                            ${agg.sentiment && agg.sentiment !== 'N/A' ? `
                                <div>
                                    Sentiment: ${agg.sentiment} 
                                    <span class="confidence">(${((agg.sentiment_confidence || 0) * 100).toFixed(1)}%)</span>
                                </div>
                            ` : ''}
                        </div>
                        <div class="item-detail" style="color: #888; font-size: 0.85em; margin-top: 5px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                            <span>Window: ${formatTimeWindow(result.window_start, result.window_end)}</span>
                            <span>Chunks: ${result.chunk_count || 0} | Session: ${result.session_id.substring(result.session_id.length - 8)}</span>
                        </div>
                    </li>
                `;
            }).join('');
        }
        
        async function fetchDashboardData() {
            try {
                const response = await fetch('/ser/api/dashboard/status');
                const data = await response.json();
                
                updateQueue(data.queue || []);
                updateProcessing(data.processing || []);
                updateResults(data.results || []);
                updateAggregated(data.aggregated || []);
                
                document.getElementById('queueSize').textContent = data.queue_size || 0;
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                document.getElementById('statusIndicator').className = 'status-indicator status-online';
                document.getElementById('statusText').textContent = 'Connected';
                
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
                document.getElementById('statusIndicator').className = 'status-indicator status-offline';
                document.getElementById('statusText').textContent = 'Disconnected';
            }
        }
        
        // Aggregation interval functions
        let aggregationIntervalInputFocused = false;
        
        async function loadAggregationInterval() {
            try {
                const response = await fetch('/ser/api/aggregation-interval');
                const data = await response.json();
                const input = document.getElementById('aggregationIntervalInput');
                if (input && !aggregationIntervalInputFocused) {
                    input.value = data.interval_seconds || 300;
                }
            } catch (error) {
                console.error('Error loading aggregation interval:', error);
            }
        }
        
        async function setAggregationInterval() {
            const input = document.getElementById('aggregationIntervalInput');
            const interval = parseInt(input.value);
            
            if (isNaN(interval) || interval < 60 || interval > 3600) {
                alert('Interval must be between 60 and 3600 seconds');
                return;
            }
            
            try {
                const response = await fetch('/ser/api/aggregation-interval', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({interval_seconds: interval})
                });
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('Aggregation interval set to', data.interval_seconds, 'seconds');
                } else {
                    const error = await response.json();
                    alert('Error: ' + error.error);
                }
            } catch (error) {
                console.error('Error setting aggregation interval:', error);
                alert('Failed to set aggregation interval');
            }
        }
        
        // Track input focus state
        document.addEventListener('DOMContentLoaded', function() {
            const input = document.getElementById('aggregationIntervalInput');
            if (input) {
                input.addEventListener('focus', () => {
                    aggregationIntervalInputFocused = true;
                });
                input.addEventListener('blur', () => {
                    aggregationIntervalInputFocused = false;
                });
            }
        });
        
        // Initial load
        fetchDashboardData();
        loadAggregationInterval();
        
        // Poll every 2 seconds
        setInterval(fetchDashboardData, 2000);
        setInterval(loadAggregationInterval, 2000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


def _read_aggregated_results(limit: int = 100) -> List[Dict]:
    """
    Read aggregated results from in-memory storage.

    Args:
        limit: Maximum number of results to return

    Returns:
        List of aggregated result dictionaries
    """
    try:
        # Get aggregated results from in-memory storage
        aggregated_results = read_aggregated_results(limit=limit)
        return aggregated_results

    except Exception as e:
        logger.error(f"Error reading aggregated results from memory: {e}", exc_info=True)
        return []


@router.get("/api/dashboard/status")
async def get_dashboard_status():
    """Get current dashboard status (queue, processing, results, aggregated)."""
    try:
        queue_manager = QueueManager.get_instance()
        
        # Get queue status
        queue_size = queue_manager.get_queue_size()
        queue_items = queue_manager.get_queue_items()
        
        # Get processing status
        processing_item = queue_manager.get_processing_item()
        processing_items = [processing_item] if processing_item else []
        
        # Get recent results from QueueManager (most recent processing results)
        recent_results = queue_manager.get_recent_results(limit=50)
        
        # Database queries disabled in SER service deployment
        # (fusion module not available, avoiding ModuleNotFoundError)
        
        # Sort by timestamp (newest first)
        recent_results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Return last 50 results
        recent_results = recent_results[:50]
        
        # Get aggregated results from log file
        aggregated_results = _read_aggregated_results(limit=100)
        
        return {
            "queue_size": queue_size,
            "queue": queue_items,
            "processing": processing_items,
            "results": recent_results,
            "aggregated": aggregated_results
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard status: {e}", exc_info=True)
        return {
            "queue_size": 0,
            "queue": [],
            "processing": [],
            "results": [],
            "aggregated": [],
            "error": str(e)
        }


class AggregationIntervalRequest(BaseModel):
    """Request model for setting aggregation interval."""
    interval_seconds: int


@router.get("/api/aggregation-interval")
async def get_aggregation_interval():
    """Get current aggregation interval."""
    try:
        manager = AggregationIntervalManager.get_instance()
        return manager.get_status()
    except Exception as e:
        logger.error(f"Error getting aggregation interval: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )


@router.post("/api/aggregation-interval")
async def set_aggregation_interval(request: AggregationIntervalRequest):
    """Set aggregation interval."""
    try:
        manager = AggregationIntervalManager.get_instance()
        manager.set_interval(request.interval_seconds)
        return {"status": "success", "interval_seconds": request.interval_seconds}
    except ValueError as e:
        logger.warning(f"Invalid aggregation interval: {e}")
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )
    except Exception as e:
        logger.error(f"Error setting aggregation interval: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )


