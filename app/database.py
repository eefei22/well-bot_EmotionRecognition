"""
SER Service Database Functions

Centralized database operations for SER service.
Handles writing voice emotion results and querying for fusion service.
"""

import logging
import sys
import os
from typing import Optional, Dict, List
from datetime import datetime

# Add parent directory to path to import utils.database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from utils import database as cloud_database
except ImportError:
    # Fallback: try importing from Well-Bot_cloud if SER is separate
    cloud_database = None

logger = logging.getLogger(__name__)

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


def _map_ser_emotion_to_fusion(ser_emotion: str) -> Optional[str]:
    """
    Map SER emotion label to fusion emotion label.
    
    Args:
        ser_emotion: SER emotion label (e.g., "hap", "sad", "ang", "fea", "neu", "dis", "sur")
    
    Returns:
        Fusion emotion label ("Angry", "Sad", "Happy", "Fear") or None if not mappable
    """
    ser_emotion_lower = ser_emotion.lower()
    return SER_TO_FUSION_EMOTION_MAP.get(ser_emotion_lower)


def get_malaysia_timezone():
    """Get Malaysia timezone (UTC+8)."""
    if cloud_database:
        return cloud_database.get_malaysia_timezone()
    else:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo("Asia/Kuala_Lumpur")
        except (ImportError, Exception):
            try:
                import pytz
                return pytz.timezone("Asia/Kuala_Lumpur")
            except ImportError:
                from datetime import timezone, timedelta
                return timezone(timedelta(hours=8))


def get_malaysia_timezone():
    """Get Malaysia timezone (UTC+8)."""
    if cloud_database:
        return cloud_database.get_malaysia_timezone()
    else:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo("Asia/Kuala_Lumpur")
        except (ImportError, Exception):
            try:
                import pytz
                return pytz.timezone("Asia/Kuala_Lumpur")
            except ImportError:
                from datetime import timezone, timedelta
                return timezone(timedelta(hours=8))


def _get_supabase_client():
    """
    Get Supabase client instance.
    
    Returns:
        Supabase Client instance
    """
    if cloud_database:
        return cloud_database.get_supabase_client()
    else:
        # Fallback: try to import directly
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        return create_client(url, key)


def insert_voice_emotion(
    user_id: str,
    timestamp: datetime,
    analysis_result: dict,
    audio_metadata: dict,
    is_synthetic: bool = False
) -> Optional[Dict]:
    """
    Write SER result directly to voice_emotion table.
    
    Args:
        user_id: UUID of the user
        timestamp: Timestamp when audio was captured
        analysis_result: Dictionary with emotion, emotion_confidence, transcript, language, sentiment, sentiment_confidence
        audio_metadata: Dictionary with sample_rate, frame_size_ms, frame_stride_ms, duration_sec
        is_synthetic: Whether this is synthetic/simulation data (default: False)
    
    Returns:
        Dictionary with inserted record data, or None if failed
    """
    try:
        client = _get_supabase_client()
        malaysia_tz = get_malaysia_timezone()
        
        # Ensure timestamp is timezone-aware (UTC+8)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=malaysia_tz)
        else:
            timestamp = timestamp.astimezone(malaysia_tz)
        
        # Convert timestamp to ISO format string (timezone-naive for database)
        timestamp_str = timestamp.isoformat()
        
        # Map SER emotion to database format (keep original SER emotion label)
        predicted_emotion = analysis_result.get("emotion", "unknown")
        emotion_confidence = analysis_result.get("emotion_confidence", 0.0)
        
        # Prepare data for insertion
        data = {
            "user_id": user_id,
            "timestamp": timestamp_str,
            "sample_rate": audio_metadata.get("sample_rate", 16000),
            "frame_size_ms": audio_metadata.get("frame_size_ms", 25.0),
            "frame_stride_ms": audio_metadata.get("frame_stride_ms", 10.0),
            "duration_sec": audio_metadata.get("duration_sec", 10.0),
            "predicted_emotion": predicted_emotion,
            "emotion_confidence": emotion_confidence,
        }
        
        # Add optional fields
        if analysis_result.get("transcript"):
            data["transcript"] = analysis_result["transcript"]
        if analysis_result.get("language"):
            data["language"] = analysis_result["language"]
        if analysis_result.get("sentiment"):
            data["sentiment"] = analysis_result["sentiment"]
        if analysis_result.get("sentiment_confidence") is not None:
            data["sentiment_confidence"] = analysis_result["sentiment_confidence"]
        
        # Store is_synthetic flag in a metadata field if available
        # For now, we'll add it as a comment/metadata field if the table supports it
        # If the table doesn't have a metadata field, we'll need to add a column via migration
        # For now, we'll skip storing it and handle it in queries if needed
        
        # Insert into database
        response = client.table("voice_emotion")\
            .insert(data)\
            .execute()
        
        if response.data and len(response.data) > 0:
            inserted_record = response.data[0]
            logger.info(
                f"Inserted voice emotion for user {user_id}: {predicted_emotion} "
                f"(confidence: {emotion_confidence:.2f}, synthetic: {is_synthetic})"
            )
            return inserted_record
        else:
            logger.warning(f"Insert returned no data for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Failed to insert voice emotion for user {user_id}: {e}", exc_info=True)
        return None


def query_voice_emotion_signals(
    user_id: str,
    start_time: datetime,
    end_time: datetime,
    include_synthetic: bool = True
) -> List[Dict]:
    """
    Query voice_emotion table and return ModelSignal objects.
    
    Args:
        user_id: UUID of the user
        start_time: Start of time window (inclusive, UTC+8 timezone-aware)
        end_time: End of time window (inclusive, UTC+8 timezone-aware)
        include_synthetic: Whether to include synthetic data (default: True)
    
    Returns:
        List of dictionaries with signal data (fusion module not available in SER deployment)
    """
    try:
        client = _get_supabase_client()
        malaysia_tz = get_malaysia_timezone()
        
        # Ensure timestamps are timezone-aware (UTC+8)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=malaysia_tz)
        else:
            start_time = start_time.astimezone(malaysia_tz)
        
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=malaysia_tz)
        else:
            end_time = end_time.astimezone(malaysia_tz)
        
        # Convert to ISO format strings for database query
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()
        
        # Query database
        query = client.table("voice_emotion")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("timestamp", start_time_str)\
            .lte("timestamp", end_time_str)\
            .order("timestamp", desc=False)
        
        response = query.execute()
        
        signals = []
        for record in response.data:
            # Map SER emotion to fusion emotion
            ser_emotion = record.get("predicted_emotion", "")
            fusion_emotion = _map_ser_emotion_to_fusion(ser_emotion)
            
            # Skip if emotion is not mappable
            if fusion_emotion is None:
                logger.debug(f"Skipping unmappable emotion: {ser_emotion}")
                continue
            
            # Create dict instead of ModelSignal object (fusion module not available)
            signal = {
                "user_id": user_id,
                "timestamp": record.get("timestamp", ""),
                "modality": "speech",
                "emotion_label": fusion_emotion,
                "confidence": float(record.get("emotion_confidence", 0.0))
            }
            signals.append(signal)
        
        logger.info(
            f"Queried {len(signals)} voice emotion signals for user {user_id} "
            f"in window [{start_time_str}, {end_time_str}]"
        )
        return signals
        
    except Exception as e:
        logger.error(f"Failed to query voice emotion signals: {e}", exc_info=True)
        return []


def insert_face_emotion_synthetic(
    user_id: str,
    timestamp: datetime,
    emotion_label: str,
    confidence: float,
    is_synthetic: bool = True
) -> Optional[Dict]:
    """
    Write synthetic FER result to face_emotion table.
    
    Args:
        user_id: UUID of the user
        timestamp: Timestamp for the emotion signal
        emotion_label: Emotion label ("Happy", "Sad", "Angry", "Fear")
        confidence: Confidence score (0.0-1.0)
        is_synthetic: Whether this is synthetic data (default: True)
    
    Returns:
        Dictionary with inserted record data, or None if failed
    """
    try:
        client = _get_supabase_client()
        malaysia_tz = get_malaysia_timezone()
        
        # Ensure timestamp is timezone-aware (UTC+8)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=malaysia_tz)
        else:
            timestamp = timestamp.astimezone(malaysia_tz)
        
        # Convert timestamp to ISO format string (without timezone for face_emotion)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        date_str = timestamp.date().isoformat()
        
        # Prepare data for insertion
        # face_emotion table schema (updated): user_id, timestamp, predicted_emotion, emotion_confidence, date
        data = {
            "user_id": user_id,
            "timestamp": timestamp_str,
            "predicted_emotion": emotion_label,
            "emotion_confidence": confidence,
            "date": date_str
        }
        
        # Insert into database
        response = client.table("face_emotion")\
            .insert(data)\
            .execute()
        
        if response.data and len(response.data) > 0:
            inserted_record = response.data[0]
            logger.info(
                f"Inserted face emotion (synthetic) for user {user_id}: {emotion_label} "
                f"(confidence: {confidence:.2f})"
            )
            return inserted_record
        else:
            logger.warning(f"Insert returned no data for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Failed to insert face emotion (synthetic) for user {user_id}: {e}", exc_info=True)
        return None


def insert_vitals_emotion_synthetic(
    user_id: str,
    timestamp: datetime,
    emotion_label: str,
    confidence: float,
    is_synthetic: bool = True
) -> Optional[Dict]:
    """
    Write synthetic Vitals-derived emotion result to bvs_emotion table.

    Note: bvs_emotion table only has emotion columns (predicted_emotion, emotion_confidence).
    Vitals signals are treated as emotion predictions derived from biometric data.

    Args:
        user_id: UUID of the user
        timestamp: Timestamp for the emotion signal
        emotion_label: Emotion label derived from vitals ("Happy", "Sad", "Angry", "Fear")
        confidence: Confidence score (0.0-1.0)
        is_synthetic: Whether this is synthetic data (default: True)

    Returns:
        Dictionary with inserted record data, or None if failed
    """
    try:
        client = _get_supabase_client()
        malaysia_tz = get_malaysia_timezone()

        # Ensure timestamp is timezone-aware (UTC+8)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=malaysia_tz)
        else:
            timestamp = timestamp.astimezone(malaysia_tz)

        # Convert timestamp to ISO format string (timezone-naive for database)
        timestamp_str = timestamp.isoformat()
        # Extract date for the date column
        date_str = timestamp.date().isoformat()

        # Prepare data for bvs_emotion table - only insert columns that exist
        # bvs_emotion table schema: user_id, timestamp, predicted_emotion, emotion_confidence, date
        data = {
            "user_id": user_id,
            "timestamp": timestamp_str,
            "predicted_emotion": emotion_label,
            "emotion_confidence": confidence,
            "date": date_str,
        }

        # Insert into bvs_emotion table
        response = client.table("bvs_emotion")\
            .insert(data)\
            .execute()

        if response.data and len(response.data) > 0:
            inserted_record = response.data[0]
            logger.info(
                f"Inserted vitals emotion (synthetic) for user {user_id}: {emotion_label} "
                f"(confidence: {confidence:.2f})"
            )
            return inserted_record
        else:
            logger.warning(f"Insert returned no data for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Failed to insert vitals emotion (synthetic) for user {user_id}: {e}", exc_info=True)
        return None


def get_last_fusion_timestamp(user_id: str) -> Optional[datetime]:
    """
    Get the timestamp of the last successful Fusion run for a user.
    
    Queries the emotional_log table for the maximum timestamp (most recent Fusion run).
    
    Args:
        user_id: UUID of the user
    
    Returns:
        Timezone-aware datetime (UTC+8) of the last Fusion run, or None if no Fusion runs exist
    """
    try:
        client = _get_supabase_client()
        malaysia_tz = get_malaysia_timezone()
        
        # Query emotional_log table for MAX(timestamp) where user_id matches
        query = client.table("emotional_log")\
            .select("timestamp")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=True)\
            .limit(1)
        
        response = query.execute()
        
        if response.data and len(response.data) > 0:
            timestamp_str = response.data[0].get("timestamp")
            if timestamp_str:
                # Parse timestamp string to datetime
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                # Ensure timezone-aware (UTC+8)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=malaysia_tz)
                else:
                    timestamp = timestamp.astimezone(malaysia_tz)
                logger.debug(f"Last Fusion timestamp for user {user_id}: {timestamp.isoformat()}")
                return timestamp
        
        # No Fusion runs found
        logger.debug(f"No Fusion runs found for user {user_id}")
        return None
        
    except Exception as e:
        logger.warning(f"Failed to query last Fusion timestamp for user {user_id}: {e}", exc_info=True)
        return None

