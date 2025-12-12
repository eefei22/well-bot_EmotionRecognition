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

from app.queue_manager import QueueManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ser", tags=["SER"])


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

    # Get current timestamp for this chunk
    timestamp = datetime.now()

    # Enqueue for processing
    queue_manager = QueueManager.get_instance()
    success = queue_manager.enqueue_chunk(user_id, tmp_path, timestamp, filename=file.filename)
    
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
