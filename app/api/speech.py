# app/api/speech.py

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import tempfile
import shutil
import logging
import uuid

from app.services.speech_ProcessingPipeline import analyze_full
from app.models.speech import VoiceEmotionCreate
from app.crud.speech import insert_voice_emotion
import torchaudio

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analyze-speech")
async def analyze_speech(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    """
    Analyze speech audio for emotion, transcription, language, and sentiment.
    
    Args:
        file: WAV audio file to analyze
        user_id: UUID of the user (required)
    
    Returns:
        Dictionary with analysis_result containing emotion, transcript, language, and sentiment
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

    # Get audio metadata before analysis
    try:
        waveform, sample_rate = torchaudio.load(tmp_path)
        # Calculate duration in seconds
        duration_sec = waveform.shape[1] / sample_rate
    except Exception as e:
        logger.warning(f"Failed to get audio metadata: {e}, using defaults")
        sample_rate = 16000  # Default sample rate
        duration_sec = 0.0

    # Analyse Speech
    analysis_result = analyze_full(tmp_path)

    # Map analysis_result fields to database schema
    try:
        voice_emotion_data = VoiceEmotionCreate(
            user_id=user_id,
            sample_rate=int(sample_rate),
            frame_size_ms=25.0,  # Common default: 25ms frames
            frame_stride_ms=10.0,  # Common default: 10ms stride
            duration_sec=float(duration_sec),
            predicted_emotion=analysis_result.get("emotion", "unknown"),
            emotion_confidence=analysis_result.get("emotion_confidence", 0.0),
            transcript=analysis_result.get("transcript", ""),
            language=analysis_result.get("language", "unknown"),
            sentiment=analysis_result.get("sentiment", "unknown"),
            sentiment_confidence=analysis_result.get("sentiment_confidence", 0.0)
        )

        # Save to database
        db_result = insert_voice_emotion(voice_emotion_data)
        logger.info(f"Saved voice emotion record to database for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to save voice emotion record to database: {e}")
        # Continue even if database save fails - still return analysis result

    # Return analysis result
    return {
        "analysis_result": analysis_result
    }

