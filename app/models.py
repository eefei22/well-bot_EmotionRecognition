"""
SER Service Pydantic Models

SER-specific data models for voice emotion recognition.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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


class ChunkResult(BaseModel):
    """Individual inference result for a single audio chunk."""
    timestamp: datetime
    emotion: str
    emotion_confidence: float
    transcript: Optional[str] = None
    language: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[float] = None


class AggregatedResult(BaseModel):
    """Aggregated result for a time window (e.g., 5 minutes)."""
    timestamp: datetime
    user_id: str
    session_id: str
    window_start: datetime
    window_end: datetime
    chunk_count: int
    emotion: str
    emotion_confidence: float
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[float] = None


class PredictRequest(BaseModel):
    """Request model for /predict endpoint (used by fusion service)."""
    user_id: str
    snapshot_timestamp: str  # ISO format timestamp
    window_seconds: int = 60  # Time window in seconds


class ModelSignal(BaseModel):
    """Model prediction signal structure (matches fusion service contract)."""
    user_id: str
    timestamp: str  # ISO format timestamp
    modality: str = "speech"  # Always "speech" for SER
    emotion_label: str  # "Angry" | "Sad" | "Happy" | "Fear"
    confidence: float  # Confidence score between 0.0 and 1.0


class ModelPredictResponse(BaseModel):
    """Response structure for /predict endpoint (matches fusion service contract)."""
    signals: list[ModelSignal] = []