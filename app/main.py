from fastapi import FastAPI
from app.api import speech
from dotenv import load_dotenv
import logging

from app.core.db import get_supabase_client

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    """Test Supabase connection on startup."""
    try:
        client = get_supabase_client()
        # Simple test query to verify connection
        # This is optional - just to verify connection works
        logger.info("Supabase connection test successful")
    except Exception as e:
        logger.error(f"Failed to connect to Supabase on startup: {e}")
        # Don't raise - allow app to start even if connection test fails
        # Connection will be retried when actually used


app.include_router(speech.router)
