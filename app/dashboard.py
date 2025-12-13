"""
Dashboard API endpoints for monitoring queue, processing, and results.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List, Dict, Optional
from datetime import datetime
import logging
import json
import os

from app.queue_manager import QueueManager
from app.database import query_voice_emotion_signals, get_malaysia_timezone, get_last_fusion_timestamp
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
    Read aggregated results from the log file and filter by fusion timestamp.
    
    Only returns aggregated results that occurred after the last Fusion run for each user.
    
    Args:
        limit: Maximum number of results to return
        
    Returns:
        List of aggregated result dictionaries (filtered by fusion timestamp)
    """
    log_file = os.path.join(settings.AGGREGATION_LOG_DIR, "aggregation_log.jsonl")
    
    if not os.path.exists(log_file):
        return []
    
    aggregated_results = []
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # Read all lines and parse JSON
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    aggregated_results.append(entry)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse aggregation log entry: {e}")
                    continue
        
        # Sort by timestamp (newest first)
        aggregated_results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Filter by fusion timestamp per user
        # Extract unique user_ids
        user_ids = set(entry.get("user_id") for entry in aggregated_results if entry.get("user_id"))
        
        # Get last Fusion timestamps for all users
        last_fusion_timestamps = {}
        for user_id in user_ids:
            try:
                last_fusion_timestamp = get_last_fusion_timestamp(user_id)
                if last_fusion_timestamp is not None:
                    last_fusion_timestamps[user_id] = last_fusion_timestamp
            except Exception as e:
                logger.debug(f"Failed to get last Fusion timestamp for user {user_id}: {e}")
                # Continue without filtering for this user if query fails
        
        # Filter aggregated results: only include entries after last Fusion run
        filtered_results = []
        malaysia_tz = get_malaysia_timezone()
        
        for entry in aggregated_results:
            user_id = entry.get("user_id", "")
            entry_timestamp_str = entry.get("timestamp", "")
            
            if not entry_timestamp_str:
                continue
            
            # Parse entry timestamp
            try:
                entry_timestamp = datetime.fromisoformat(entry_timestamp_str.replace('Z', '+00:00'))
                if entry_timestamp.tzinfo is None:
                    entry_timestamp = entry_timestamp.replace(tzinfo=malaysia_tz)
                else:
                    entry_timestamp = entry_timestamp.astimezone(malaysia_tz)
            except Exception as e:
                logger.debug(f"Failed to parse timestamp {entry_timestamp_str}: {e}")
                # Include entry if timestamp parsing fails (graceful fallback)
                filtered_results.append(entry)
                continue
            
            # Filter: only include if no Fusion run exists OR entry is after last Fusion run
            if user_id and user_id in last_fusion_timestamps:
                last_fusion_ts = last_fusion_timestamps[user_id]
                if entry_timestamp <= last_fusion_ts:
                    # Entry was already processed by Fusion, skip it
                    continue
            
            filtered_results.append(entry)
        
        # Return last N filtered results
        return filtered_results[:limit]
        
    except Exception as e:
        logger.error(f"Error reading aggregated results from {log_file}: {e}", exc_info=True)
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
        
        # Also query database for recent voice emotion records (last 24 hours)
        # This supplements QueueManager results with data that may have been written directly
        try:
            malaysia_tz = get_malaysia_timezone()
            now = datetime.now(malaysia_tz)
            start_time = now - timedelta(hours=24)
            
            # Get all unique user_ids from QueueManager results
            user_ids = set(r.get("user_id") for r in recent_results if r.get("user_id"))
            
            # If no user_ids from QueueManager, query for any recent records
            if not user_ids:
                # Query database for any recent records (we'll need to get user_ids from somewhere)
                # For now, we'll rely on QueueManager results and database will be queried per-user as needed
                pass
            else:
                # Query database for each user
                db_results = []
                for user_id in user_ids:
                    try:
                        # Get last Fusion timestamp to filter out already-processed signals
                        last_fusion_timestamp = get_last_fusion_timestamp(user_id)
                        
                        signals = query_voice_emotion_signals(
                            user_id=user_id,
                            start_time=start_time,
                            end_time=now,
                            include_synthetic=True
                        )
                        # Convert signals to result format and filter by last Fusion timestamp
                        for signal in signals:
                            # Parse timestamp
                            signal_timestamp = datetime.fromisoformat(signal["timestamp"].replace('Z', '+00:00'))
                            
                            # Filter: only include signals after last Fusion run
                            if last_fusion_timestamp is not None:
                                if signal_timestamp <= last_fusion_timestamp:
                                    # Signal was already processed by Fusion, skip it
                                    continue
                            
                            db_results.append({
                                "user_id": user_id,
                                "timestamp": signal_timestamp.isoformat(),
                                "emotion": signal["emotion_label"].lower()[:3] if len(signal["emotion_label"].lower()) >= 3 else signal["emotion_label"].lower(),  # Convert back to SER format
                                "emotion_confidence": signal["confidence"],
                                "sentiment": None,  # Not available from signal
                                "sentiment_confidence": None,
                                "transcript": None,  # Not available from signal
                                "language": None
                            })
                    except Exception as e:
                        logger.warning(f"Failed to query database for user {user_id}: {e}")
                        continue
                
                # Combine and deduplicate results (prefer QueueManager results as they're more recent)
                seen_results = {(r["user_id"], r["timestamp"]) for r in recent_results}
                
                # Add database results that aren't already in recent_results
                for result in db_results:
                    key = (result["user_id"], result["timestamp"])
                    if key not in seen_results:
                        recent_results.append(result)
                        seen_results.add(key)
        except Exception as e:
            logger.warning(f"Failed to query database for dashboard results: {e}")
        
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


