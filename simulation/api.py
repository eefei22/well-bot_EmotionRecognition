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
from .signal_storage import SignalStorage
from .demo_mode import DemoModeManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation"])


class InjectSignalsRequest(BaseModel):
    """Request model for signal injection endpoint."""
    modality: str  # "ser", "fer", "vitals"
    signals: List[ModelSignal]


class DemoModeRequest(BaseModel):
    """Request model for demo mode toggle."""
    enabled: bool


@router.post("/ser/predict", response_model=ModelPredictResponse)
async def predict_ser(
    request: PredictRequest,
    clear: bool = Query(default=True, description="Clear signals after reading")
):
    """
    Read SER signals from JSONL file within a time window.
    
    Args:
        request: PredictRequest with user_id, snapshot_timestamp, window_seconds
        clear: Whether to clear signals after reading (default: True)
    
    Returns:
        ModelPredictResponse with signals in the time window
    """
    try:
        logger.info(
            f"POST /simulation/ser/predict - Request for user {request.user_id} "
            f"(window: {request.window_seconds}s)"
        )
        
        # Parse timestamp
        snapshot_dt = datetime.fromisoformat(
            request.snapshot_timestamp.replace("Z", "+00:00")
        )
        window_start = snapshot_dt - timedelta(seconds=request.window_seconds)
        window_end = snapshot_dt
        
        # Read signals from storage
        storage = SignalStorage.get_instance()
        signals = storage.read_signals_in_window(
            "ser",
            request.user_id,
            window_start,
            window_end
        )
        
        logger.info(
            f"POST /simulation/ser/predict - Returning {len(signals)} signals "
            f"for user {request.user_id}"
        )
        
        # Clear signals if requested
        if clear and signals:
            storage.clear_signals("ser")
            logger.info("Cleared SER signals after reading")
        
        return ModelPredictResponse(signals=signals)
    
    except Exception as e:
        logger.error(f"Error in /simulation/ser/predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/fer/predict", response_model=ModelPredictResponse)
async def predict_fer(
    request: PredictRequest,
    clear: bool = Query(default=True, description="Clear signals after reading")
):
    """
    Read FER signals from JSONL file within a time window.
    
    Args:
        request: PredictRequest with user_id, snapshot_timestamp, window_seconds
        clear: Whether to clear signals after reading (default: True)
    
    Returns:
        ModelPredictResponse with signals in the time window
    """
    try:
        logger.info(
            f"POST /simulation/fer/predict - Request for user {request.user_id} "
            f"(window: {request.window_seconds}s)"
        )
        
        # Parse timestamp
        snapshot_dt = datetime.fromisoformat(
            request.snapshot_timestamp.replace("Z", "+00:00")
        )
        window_start = snapshot_dt - timedelta(seconds=request.window_seconds)
        window_end = snapshot_dt
        
        # Read signals from storage
        storage = SignalStorage.get_instance()
        signals = storage.read_signals_in_window(
            "fer",
            request.user_id,
            window_start,
            window_end
        )
        
        logger.info(
            f"POST /simulation/fer/predict - Returning {len(signals)} signals "
            f"for user {request.user_id}"
        )
        
        # Clear signals if requested
        if clear and signals:
            storage.clear_signals("fer")
            logger.info("Cleared FER signals after reading")
        
        return ModelPredictResponse(signals=signals)
    
    except Exception as e:
        logger.error(f"Error in /simulation/fer/predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/vitals/predict", response_model=ModelPredictResponse)
async def predict_vitals(
    request: PredictRequest,
    clear: bool = Query(default=True, description="Clear signals after reading")
):
    """
    Read Vitals signals from JSONL file within a time window.
    
    Args:
        request: PredictRequest with user_id, snapshot_timestamp, window_seconds
        clear: Whether to clear signals after reading (default: True)
    
    Returns:
        ModelPredictResponse with signals in the time window
    """
    try:
        logger.info(
            f"POST /simulation/vitals/predict - Request for user {request.user_id} "
            f"(window: {request.window_seconds}s)"
        )
        
        # Parse timestamp
        snapshot_dt = datetime.fromisoformat(
            request.snapshot_timestamp.replace("Z", "+00:00")
        )
        window_start = snapshot_dt - timedelta(seconds=request.window_seconds)
        window_end = snapshot_dt
        
        # Read signals from storage
        storage = SignalStorage.get_instance()
        signals = storage.read_signals_in_window(
            "vitals",
            request.user_id,
            window_start,
            window_end
        )
        
        logger.info(
            f"POST /simulation/vitals/predict - Returning {len(signals)} signals "
            f"for user {request.user_id}"
        )
        
        # Clear signals if requested
        if clear and signals:
            storage.clear_signals("vitals")
            logger.info("Cleared Vitals signals after reading")
        
        return ModelPredictResponse(signals=signals)
    
    except Exception as e:
        logger.error(f"Error in /simulation/vitals/predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
        
        # Write signals to storage
        storage = SignalStorage.get_instance()
        for signal in request.signals:
            storage.write_signal(modality, signal)
        
        logger.info(
            f"Injected {len(request.signals)} signals for {modality} modality"
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

