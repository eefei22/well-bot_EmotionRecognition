# app/models/speech.py
from pydantic import BaseModel
from typing import Optional

class VoiceEmotionCreate(BaseModel):
    """Model for creating voice emotion records in voice_emotion table."""
    user_id: str
    sample_rate: int  # Required: audio sample rate
    frame_size_ms: float  # Required: frame size in milliseconds
    frame_stride_ms: float  # Required: frame stride in milliseconds
    duration_sec: float  # Required: audio duration in seconds
    predicted_emotion: str  # Matches existing column name
    emotion_confidence: float  # Matches existing column name
    transcript: Optional[str] = None
    language: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[float] = None
