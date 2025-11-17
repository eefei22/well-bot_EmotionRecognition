from fastapi import FastAPI
from app.api import speech
from dotenv import load_dotenv
import logging
import asyncio

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Well-Bot Speech Emotion Recognition API",
    description="Speech emotion recognition, transcription, language detection, and sentiment analysis",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Well-Bot SER API is running", "status": "healthy"}


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Test Supabase connection on startup (non-blocking)."""
    # Run in background to not block startup
    async def test_connection():
        try:
            from app.core.db import get_supabase_client
            client = get_supabase_client()
            logger.info("Supabase connection test successful")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase on startup: {e}")
            # Don't raise - allow app to start even if connection test fails
            # Connection will be retried when actually used
    
    # Start connection test in background
    asyncio.create_task(test_connection())


app.include_router(speech.router)
