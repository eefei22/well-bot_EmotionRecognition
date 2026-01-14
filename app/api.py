"""
SER Service API Routes

FastAPI routes for speech emotion recognition endpoints and dashboard.
"""

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import tempfile
import shutil
import logging
import uuid
import os
from datetime import datetime
from typing import List

from app.queue_manager import QueueManager
from app.models import PredictRequest, ModelPredictResponse, ModelSignal
from app.database import get_malaysia_timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ser", tags=["SER"])

# Separate router for fusion service endpoints (no prefix)
fusion_router = APIRouter(tags=["SER Fusion"])


@router.post("/analyze-speech")
async def analyze_speech(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    """
    Enqueue audio chunk for asynchronous processing.
    
    Args:
        file: WAV audio file to analyze (10-second chunk)
        user_id: UUID of the user (required)
    
    Returns:
        Dictionary with status indicating the chunk was queued
    """
    # Validate user_id is a valid UUID format
    try:
        uuid.UUID(user_id)
    except ValueError:
        return JSONResponse(
            status_code=400, 
            content={"error": f"Invalid user_id format: {user_id}. Must be a valid UUID."}
        )
    
    if not file.filename.endswith(".wav"):
        return JSONResponse(status_code=400, content={"error": "Only .wav files are supported."})

    # Save uploaded file to a temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
    finally:
        file.file.close()

    # Get current timestamp for this chunk (Malaysia timezone)
    timestamp = datetime.now(get_malaysia_timezone())

    # Enqueue for processing
    queue_manager = QueueManager.get_instance()
    # Ensure we have a filename for tracking
    filename_for_queue = file.filename or f"audio_chunk_{timestamp.strftime('%Y%m%d_%H%M%S')}.wav"
    success = queue_manager.enqueue_chunk(user_id, tmp_path, timestamp, filename=filename_for_queue)
    
    if not success:
        # Clean up temp file if enqueue failed
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to enqueue audio chunk for processing"}
        )

    logger.info(
        f"Enqueued audio chunk for user {user_id} "
        f"(queue size: {queue_manager.get_queue_size()})"
    )

    # Return immediate acknowledgment
    return {
        "status": "queued",
        "message": "Audio chunk queued for processing",
        "queue_size": queue_manager.get_queue_size()
    }


# Mapping from SER emotion labels to fusion emotion labels
SER_TO_FUSION_EMOTION_MAP = {
    # 7-class format
    "ang": "Angry",
    "sad": "Sad",
    "hap": "Happy",
    "fea": "Fear",
    # 9-class format
    "angry": "Angry",
    "happy": "Happy",
    "fearful": "Fear",
    "fear": "Fear",
    # Neutral and other emotions are not mapped (will be skipped)
}


def _map_ser_emotion_to_fusion(ser_emotion: str) -> str | None:
    """
    Map SER emotion label to fusion emotion label.
    
    Args:
        ser_emotion: SER emotion label (e.g., "hap", "sad", "ang", "fea", "neu", "dis", "sur")
    
    Returns:
        Fusion emotion label ("Angry", "Sad", "Happy", "Fear") or None if not mappable
    """
    ser_emotion_lower = ser_emotion.lower()
    return SER_TO_FUSION_EMOTION_MAP.get(ser_emotion_lower)


# Note: /predict endpoint removed - Fusion service now queries database directly


@router.get("/status")
async def get_ser_service_status():
    """
    Get detailed SER service status for cloud dashboard monitoring.

    Returns real-time information about:
    - Recent requests received
    - Current processing status
    - Processing results and database write status
    """
    try:
        from app.queue_manager import QueueManager
        from app.database import get_malaysia_timezone
        from datetime import datetime, timedelta

        queue_manager = QueueManager.get_instance()
        malaysia_tz = get_malaysia_timezone()
        now = datetime.now(malaysia_tz)

        # Get queue status
        queue_size = queue_manager.get_queue_size()
        queue_items = queue_manager.get_queue_items()

        # Get processing status
        processing_item = queue_manager.get_processing_item()
        processing_status = None
        if processing_item:
            processing_status = {
                "user_id": processing_item.get("user_id"),
                "started_at": processing_item.get("started_at"),
                "filename": processing_item.get("filename"),
                "status": "processing"
            }

        # Get recent results from QueueManager only
        recent_results = queue_manager.get_recent_results(limit=20)

        # Convert QueueManager results to enhanced format
        enhanced_results = []
        for result in recent_results:
            result_dict = dict(result)  # Convert to dict if it's not already

            # Database writes happen through aggregation (every 5 minutes by default)
            # Individual chunk results are processed but final database writes occur during aggregation
            db_write_success = result_dict.get("db_write_success", False)

            # Add processing completion info
            enhanced_result = {
                "user_id": result_dict.get("user_id"),
                "timestamp": result_dict.get("timestamp"),
                "filename": result_dict.get("filename", "processed.wav"),
                "emotion": result_dict.get("emotion"),
                "emotion_confidence": result_dict.get("emotion_confidence"),
                "sentiment": result_dict.get("sentiment"),
                "transcript": result_dict.get("transcript"),
                "language": result_dict.get("language"),
                "db_write_success": db_write_success,
                "aggregation_pending": True,  # Final aggregation happens every 5 minutes
                "status": "completed"
            }
            enhanced_results.append(enhanced_result)

        # Get recent requests (last 10 minutes)
        recent_requests = []
        ten_minutes_ago = now - timedelta(minutes=10)

        for item in queue_items[-20:]:  # Check last 20 queue items
            try:
                item_time = datetime.fromisoformat(item["timestamp"].replace('Z', '+00:00'))
                if item_time >= ten_minutes_ago:
                    recent_requests.append({
                        "user_id": item["user_id"],
                        "timestamp": item["timestamp"],
                        "filename": item.get("filename"),
                        "status": "queued"
                    })
            except:
                continue

        # Sort recent requests by timestamp (newest first)
        recent_requests.sort(key=lambda x: x["timestamp"], reverse=True)
        recent_requests = recent_requests[:10]  # Keep only 10 most recent

        return {
            "service": "ser",
            "timestamp": now.isoformat(),
            "status": "healthy",
            "queue_size": queue_size,
            "recent_requests": recent_requests,
            "current_processing": processing_status,
            "recent_results": enhanced_results[-10:],  # Last 10 results (most recent)
            "uptime": "unknown"  # Could be enhanced with actual uptime tracking
        }

    except Exception as e:
        logger.error(f"Error getting SER service status: {e}", exc_info=True)
        return {
            "service": "ser",
            "timestamp": datetime.now(get_malaysia_timezone()).isoformat(),
            "status": "error",
            "error": str(e),
            "queue_size": 0,
            "recent_requests": [],
            "current_processing": None,
            "recent_results": []
        }