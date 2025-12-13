"""
Well-Bot Speech Emotion Recognition (SER) Service

Main FastAPI application entry point for the SER service.
"""

from fastapi import FastAPI
from dotenv import load_dotenv
import logging
import os
import asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Well-Bot Speech Emotion Recognition API",
    description="Speech emotion recognition, transcription, language detection, and sentiment analysis",
    version="2.0.0"
)

# Import SER routes
from . import api as ser_api
from . import dashboard as ser_dashboard
from .queue_manager import QueueManager

# Import simulation routes
from simulation import api as simulation_api
from simulation import dashboard as simulation_dashboard
from simulation.demo_mode import DemoModeManager
from simulation.generation_interval import GenerationIntervalManager
from simulation.signal_generator import generate_and_send_signals
from simulation.modality_toggle import ModalityToggleManager
from simulation.user_id import UserIdManager

# Include SER service routes
app.include_router(ser_api.router)
app.include_router(ser_dashboard.router)

# Include simulation routes
app.include_router(simulation_api.router)
app.include_router(simulation_dashboard.router)

# Background task flag
_auto_generation_task = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Well-Bot SER API is running",
        "status": "healthy",
        "version": "2.0.0",
        "dashboards": {
            "ser": "/ser/dashboard",
            "simulation": "/simulation/dashboard"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    try:
        queue_manager = QueueManager.get_instance()
        
        return {
            "status": "healthy",
            "queue_manager": "running" if queue_manager.is_running() else "stopped",
            "queue_size": queue_manager.get_queue_size()
        }
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {"status": "unhealthy", "error": str(e)}


async def auto_signal_generation_task():
    """
    Background task that automatically generates signals when demo mode is enabled.
    Runs continuously, checking demo mode status and using configurable interval.
    """
    demo_manager = DemoModeManager.get_instance()
    interval_manager = GenerationIntervalManager.get_instance()
    toggle_manager = ModalityToggleManager.get_instance()
    user_id_manager = UserIdManager.get_instance()
    modalities = ["ser", "fer", "vitals"]
    
    logger.info("Auto signal generation task started")
    
    while True:
        try:
            # Get current interval from manager (can be changed via dashboard)
            interval = interval_manager.get_interval()
            
            if demo_manager.is_enabled():
                # Generate signals only for enabled modalities
                generated_count = 0
                for modality in modalities:
                    # Check if this modality is enabled
                    if toggle_manager.is_enabled(modality):
                        try:
                            # Get user_id from UserIdManager
                            current_user_id = user_id_manager.get_user_id()
                            await generate_and_send_signals(
                                modality=modality,
                                user_id=current_user_id,
                                count=1,
                                cloud_url=None  # Write locally since we're in the same service
                            )
                            generated_count += 1
                        except Exception as e:
                            logger.warning(f"Error generating {modality} signals: {e}")
                    else:
                        logger.debug(f"Skipping {modality} generation (disabled)")
                
                if generated_count > 0:
                    logger.debug(f"Auto-generated signals for {generated_count} enabled modalities (demo mode ON, interval: {interval}s)")
            else:
                logger.debug("Demo mode OFF, skipping signal generation")
            
            # Wait before next check (use current interval setting)
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            logger.info("Auto signal generation task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in auto signal generation task: {e}", exc_info=True)
            await asyncio.sleep(interval)


@app.on_event("startup")
async def startup_event():
    """Initialize SER background services on startup."""
    global _auto_generation_task
    
    logger.info("=" * 60)
    logger.info("Starting SER service background services...")
    
    # Start QueueManager worker thread
    try:
        queue_manager = QueueManager.get_instance()
        queue_manager.start_worker()
        logger.info("✓ QueueManager worker thread started")
    except Exception as e:
        logger.error(f"Failed to start QueueManager: {e}", exc_info=True)
    
    # Start auto signal generation background task
    try:
        _auto_generation_task = asyncio.create_task(auto_signal_generation_task())
        logger.info("✓ Auto signal generation task started")
    except Exception as e:
        logger.error(f"Failed to start auto signal generation task: {e}", exc_info=True)
    
    logger.info("SER service startup completed")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown SER background services."""
    global _auto_generation_task
    
    logger.info("=" * 60)
    logger.info("Shutting down SER service background services...")
    
    # Cancel auto signal generation task
    if _auto_generation_task:
        try:
            _auto_generation_task.cancel()
            try:
                await _auto_generation_task
            except asyncio.CancelledError:
                pass
            logger.info("✓ Auto signal generation task stopped")
        except Exception as e:
            logger.error(f"Error stopping auto signal generation task: {e}", exc_info=True)
    
    # Stop QueueManager
    try:
        queue_manager = QueueManager.get_instance()
        queue_manager.stop_worker()
        logger.info("✓ QueueManager stopped")
    except Exception as e:
        logger.error(f"Error stopping QueueManager: {e}", exc_info=True)
    
    logger.info("SER service shutdown completed")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    # Run the server
    # Cloud Run sets PORT env var, default to 8008 for local development
    port = int(os.getenv("PORT", "8008"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )

