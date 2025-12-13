"""
Simulation API Endpoints

FastAPI routes for simulation endpoints (predict, demo mode, signal injection).
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

from app.models import PredictRequest, ModelPredictResponse, ModelSignal
from app.database import insert_voice_emotion, insert_face_emotion_synthetic, insert_vitals_emotion_synthetic, get_malaysia_timezone
from datetime import datetime
from .demo_mode import DemoModeManager
from .emotion_bias import EmotionBiasManager
from .generation_interval import GenerationIntervalManager
from .modality_toggle import ModalityToggleManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation"])


class InjectSignalsRequest(BaseModel):
    """Request model for signal injection endpoint."""
    modality: str  # "ser", "fer", "vitals"
    signals: List[ModelSignal]


class DemoModeRequest(BaseModel):
    """Request model for demo mode toggle."""
    enabled: bool


class EmotionBiasRequest(BaseModel):
    """Request model for emotion bias setting."""
    modality: str  # "ser", "fer", "vitals"
    emotion: Optional[str]  # "Happy", "Sad", "Fear", "Angry", or None to clear


class GenerationIntervalRequest(BaseModel):
    """Request model for generation interval setting."""
    interval: int  # Interval in seconds


# Note: /simulation/{modality}/predict endpoints removed - Fusion service now queries database directly


@router.get("/demo-mode")
async def get_demo_mode():
    """
    Get current demo mode status.
    
    Returns:
        Dictionary with 'enabled' key (true/false)
    """
    try:
        demo_manager = DemoModeManager.get_instance()
        status = demo_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting demo mode status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/demo-mode")
async def set_demo_mode(request: DemoModeRequest):
    """
    Toggle demo mode state.
    
    Args:
        request: DemoModeRequest with 'enabled' boolean
    
    Returns:
        Updated demo mode status
    """
    try:
        demo_manager = DemoModeManager.get_instance()
        demo_manager.set_enabled(request.enabled)
        status = demo_manager.get_status()
        
        logger.info(f"Demo mode set to: {request.enabled}")
        return status
    except Exception as e:
        logger.error(f"Error setting demo mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/emotion-bias")
async def get_all_emotion_biases():
    """
    Get emotion bias for all modalities.
    
    Returns:
        Dictionary mapping modality to bias emotion (or None)
    """
    try:
        bias_manager = EmotionBiasManager.get_instance()
        biases = bias_manager.get_all_biases()
        return biases
    except Exception as e:
        logger.error(f"Error getting emotion biases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/emotion-bias/{modality}")
async def get_emotion_bias(modality: str):
    """
    Get emotion bias for a specific modality.
    
    Args:
        modality: Modality name ("ser", "fer", "vitals")
    
    Returns:
        Dictionary with 'modality' and 'emotion' keys
    """
    try:
        modality = modality.lower()
        bias_manager = EmotionBiasManager.get_instance()
        emotion = bias_manager.get_bias(modality)
        return {"modality": modality, "emotion": emotion}
    except Exception as e:
        logger.error(f"Error getting emotion bias: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/emotion-bias")
async def set_emotion_bias(request: EmotionBiasRequest):
    """
    Set emotion bias for a specific modality.
    
    Args:
        request: EmotionBiasRequest with modality and emotion (or None to clear)
    
    Returns:
        Updated bias status
    """
    try:
        modality = request.modality.lower()
        bias_manager = EmotionBiasManager.get_instance()
        bias_manager.set_bias(modality, request.emotion)
        emotion = bias_manager.get_bias(modality)
        
        logger.info(f"Emotion bias for {modality} set to: {emotion}")
        return {"modality": modality, "emotion": emotion}
    except ValueError as e:
        logger.error(f"Invalid emotion bias request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting emotion bias: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/generation-interval")
async def get_generation_interval():
    """
    Get current signal generation interval.
    
    Returns:
        Dictionary with interval and bounds
    """
    try:
        interval_manager = GenerationIntervalManager.get_instance()
        status = interval_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting generation interval: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/generation-interval")
async def set_generation_interval(request: GenerationIntervalRequest):
    """
    Set signal generation interval.
    
    Args:
        request: GenerationIntervalRequest with interval in seconds
    
    Returns:
        Updated interval status
    """
    try:
        interval_manager = GenerationIntervalManager.get_instance()
        interval_manager.set_interval(request.interval)
        status = interval_manager.get_status()
        
        logger.info(f"Generation interval set to: {request.interval}s")
        return status
    except ValueError as e:
        logger.error(f"Invalid generation interval request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting generation interval: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/inject-signals")
async def inject_signals(request: InjectSignalsRequest):
    """
    Inject signals into the simulation storage.
    Used by signal generator to write signals.
    
    Args:
        request: InjectSignalsRequest with modality and signals list
    
    Returns:
        Success message with count of injected signals
    """
    try:
        modality = request.modality.lower()
        
        # Validate modality
        if modality not in ["ser", "fer", "vitals"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid modality: {modality}. Must be 'ser', 'fer', or 'vitals'"
            )
        
        # Write signals directly to database
        success_count = 0
        for signal in request.signals:
            # Parse timestamp from ISO string
            signal_timestamp = datetime.fromisoformat(signal.timestamp.replace('Z', '+00:00'))
            malaysia_tz = get_malaysia_timezone()
            if signal_timestamp.tzinfo is None:
                signal_timestamp = signal_timestamp.replace(tzinfo=malaysia_tz)
            else:
                signal_timestamp = signal_timestamp.astimezone(malaysia_tz)
            
            if modality == "ser":
                # Map fusion emotion back to SER emotion format
                emotion_map = {
                    "Happy": "hap",
                    "Sad": "sad",
                    "Angry": "ang",
                    "Fear": "fea"
                }
                ser_emotion = emotion_map.get(signal.emotion_label, signal.emotion_label.lower()[:3])
                analysis_result = {
                    "emotion": ser_emotion,
                    "emotion_confidence": signal.confidence,
                    "transcript": None,
                    "language": None,
                    "sentiment": None,
                    "sentiment_confidence": None
                }
                audio_metadata = {
                    "sample_rate": 16000,
                    "frame_size_ms": 25.0,
                    "frame_stride_ms": 10.0,
                    "duration_sec": 10.0
                }
                result = insert_voice_emotion(
                    user_id=signal.user_id,
                    timestamp=signal_timestamp,
                    analysis_result=analysis_result,
                    audio_metadata=audio_metadata,
                    is_synthetic=True
                )
                if result:
                    success_count += 1
            elif modality == "fer":
                result = insert_face_emotion_synthetic(
                    user_id=signal.user_id,
                    timestamp=signal_timestamp,
                    emotion_label=signal.emotion_label,
                    confidence=signal.confidence,
                    is_synthetic=True
                )
                if result:
                    success_count += 1
            elif modality == "vitals":
                result = insert_vitals_emotion_synthetic(
                    user_id=signal.user_id,
                    timestamp=signal_timestamp,
                    emotion_label=signal.emotion_label,
                    confidence=signal.confidence,
                    is_synthetic=True
                )
                if result:
                    success_count += 1
        
        logger.info(
            f"Injected {success_count}/{len(request.signals)} signals to database for {modality} modality"
        )
        
        return {
            "status": "success",
            "modality": modality,
            "signals_injected": len(request.signals)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error injecting signals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/modality-toggle")
async def get_modality_toggles():
    """
    Get current modality toggle states.
    
    Returns:
        Dictionary with enabled state for each modality
    """
    try:
        toggle_manager = ModalityToggleManager.get_instance()
        return toggle_manager.get_status()
    except Exception as e:
        logger.error(f"Error getting modality toggles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/modality-toggle")
async def set_modality_toggle(request: dict):
    """
    Set modality generation toggle state.
    
    Args:
        request: Dictionary with 'modality' and 'enabled' keys
    
    Returns:
        Updated toggle state
    """
    try:
        modality = request.get("modality", "").lower()
        enabled = request.get("enabled", False)
        
        if modality not in ["ser", "fer", "vitals"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid modality: {modality}. Must be 'ser', 'fer', or 'vitals'"
            )
        
        toggle_manager = ModalityToggleManager.get_instance()
        toggle_manager.set_enabled(modality, enabled)
        
        return toggle_manager.get_status()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting modality toggle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


