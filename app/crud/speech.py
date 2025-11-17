# app/crud/speech.py
from app.core.db import get_supabase_client
from app.models.speech import VoiceEmotionCreate
import logging
from datetime import datetime

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
