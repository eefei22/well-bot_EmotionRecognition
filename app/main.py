"""
Well-Bot Speech Emotion Recognition (SER) Service

Main FastAPI application entry point for the SER service.
"""

from fastapi import FastAPI
from dotenv import load_dotenv
import logging
import os

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
from .aggregator import Aggregator

# Include SER service routes
app.include_router(ser_api.router)
app.include_router(ser_dashboard.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Well-Bot SER API is running",
        "status": "healthy",
        "version": "2.0.0",
        "dashboard": "/ser/dashboard"
    }


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    try:
        queue_manager = QueueManager.get_instance()
        aggregator = Aggregator.get_instance()
        
        return {
            "status": "healthy",
            "queue_manager": "running" if queue_manager.is_running() else "stopped",
            "aggregator": "running" if aggregator.is_running() else "stopped",
            "queue_size": queue_manager.get_queue_size()
        }
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {"status": "unhealthy", "error": str(e)}


@app.on_event("startup")
async def startup_event():
    """Initialize SER background services on startup."""
    logger.info("=" * 60)
    logger.info("Starting SER service background services...")
    
    # Start QueueManager worker thread
    try:
        queue_manager = QueueManager.get_instance()
        queue_manager.start_worker()
        logger.info("✓ QueueManager worker thread started")
    except Exception as e:
        logger.error(f"Failed to start QueueManager: {e}", exc_info=True)
    
    # Start Aggregator periodic timer
    try:
        aggregator = Aggregator.get_instance()
        aggregator.start_periodic_aggregation()
        logger.info("✓ Aggregator periodic timer started")
    except Exception as e:
        logger.error(f"Failed to start Aggregator: {e}", exc_info=True)
    
    logger.info("SER service startup completed")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown SER background services."""
    logger.info("=" * 60)
    logger.info("Shutting down SER service background services...")
    
    # Stop Aggregator
    try:
        aggregator = Aggregator.get_instance()
        aggregator.stop_periodic_aggregation()
        logger.info("✓ Aggregator stopped")
    except Exception as e:
        logger.error(f"Error stopping Aggregator: {e}", exc_info=True)
    
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

