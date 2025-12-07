# app/crud/speech.py
from app.core.db import get_supabase_client
from app.models.speech import VoiceEmotionCreate, ModelSignal
import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


def insert_voice_emotion(data: VoiceEmotionCreate) -> dict:
    """
    Insert a voice emotion record into the voice_emotion table.
    
    Args:
        data: VoiceEmotionCreate model instance with emotion analysis data
    
    Returns:
        Dictionary with inserted record data or error information
    
    Raises:
        Exception: If database operation fails
    """
    try:
        client = get_supabase_client()
        
        # Convert Pydantic model to dict for Supabase, excluding None values
        payload = data.dict(exclude_none=True)
        
        # Add required timestamp (current time)
        payload["timestamp"] = datetime.now().isoformat()
        
        # Insert into voice_emotion table
        response = client.table("voice_emotion")\
            .insert(payload)\
            .execute()
        
        if response.data and len(response.data) > 0:
            inserted_record = response.data[0]
            logger.info(f"Successfully inserted voice emotion record for user {data.user_id}")
            return {
                "success": True,
                "data": inserted_record
            }
        else:
            logger.warning(f"No data returned from voice_emotion insert for user {data.user_id}")
            return {
                "success": False,
                "error": "No data returned from database"
            }
    except Exception as e:
        logger.error(f"Failed to insert voice emotion record for user {data.user_id}: {e}")
        raise


def query_voice_emotion_by_window(
    user_id: str,
    snapshot_timestamp: str,
    window_seconds: int = 60
) -> List[ModelSignal]:
    """
    Query voice_emotion table for records within the specified time window.
    
    Args:
        user_id: UUID of the user
        snapshot_timestamp: ISO format timestamp string for the snapshot
        window_seconds: Time window in seconds to look back from snapshot_timestamp
    
    Returns:
        List of ModelSignal objects representing emotion predictions within the window
    
    Raises:
        Exception: If database operation fails
    """
    try:
        client = get_supabase_client()
        
        # Parse snapshot timestamp
        snapshot_dt = datetime.fromisoformat(snapshot_timestamp.replace('Z', '+00:00'))
        
        # Calculate window start time
        window_start = snapshot_dt - timedelta(seconds=window_seconds)
        
        # Query voice_emotion table
        # Filter by user_id and timestamp within window
        response = client.table("voice_emotion")\
            .select("id, user_id, timestamp, predicted_emotion, emotion_confidence")\
            .eq("user_id", user_id)\
            .gte("timestamp", window_start.isoformat())\
            .lte("timestamp", snapshot_timestamp)\
            .order("timestamp", desc=False)\
            .execute()
        
        signals = []
        if response.data:
            for record in response.data:
                # Map database record to ModelSignal
                # Map emotion labels to match fusion service expectations
                emotion_label = record.get("predicted_emotion", "unknown")
                
                # Normalize emotion label (capitalize first letter)
                if emotion_label:
                    emotion_label = emotion_label.capitalize()
                    # Map common variations to standard labels
                    emotion_mapping = {
                        "Angry": "Angry",
                        "Sad": "Sad",
                        "Happy": "Happy",
                        "Fear": "Fear",
                        "Neutral": "Happy",  # Map neutral to happy as fallback
                        "Unknown": "Happy"   # Map unknown to happy as fallback
                    }
                    emotion_label = emotion_mapping.get(emotion_label, emotion_label)
                
                # Only include valid emotions
                valid_emotions = ["Angry", "Sad", "Happy", "Fear"]
                if emotion_label not in valid_emotions:
                    logger.debug(f"Skipping invalid emotion label: {emotion_label}")
                    continue
                
                signal = ModelSignal(
                    user_id=record.get("user_id"),
                    timestamp=record.get("timestamp"),
                    modality="speech",
                    emotion_label=emotion_label,
                    confidence=float(record.get("emotion_confidence", 0.0))
                )
                signals.append(signal)
        
        logger.info(f"Queried {len(signals)} voice emotion signals for user {user_id} within {window_seconds}s window")
        return signals
        
    except Exception as e:
        logger.error(f"Failed to query voice emotion records for user {user_id}: {e}")
        raise
