# app/models/speech.py
from pydantic import BaseModel, Field
from typing import Optional, List

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


class ModelPredictRequest(BaseModel):
    """Request model for /predict endpoint (used by fusion service)."""
    user_id: str = Field(..., description="UUID of the user")
    snapshot_timestamp: str = Field(..., description="Snapshot timestamp in ISO format")
    window_seconds: int = Field(default=60, description="Time window in seconds to look back")


class ModelSignal(BaseModel):
    """Model prediction signal structure (matches fusion service contract)."""
    user_id: str
    timestamp: str  # ISO format timestamp
    modality: str = "speech"  # Always "speech" for SER service
    emotion_label: str  # "Angry" | "Sad" | "Happy" | "Fear"
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


class ModelPredictResponse(BaseModel):
    """Response structure from /predict endpoint (matches fusion service contract)."""
    signals: List[ModelSignal] = Field(default_factory=list, description="List of predictions within the time window")
