from fastapi import APIRouter
from app.api import speech

api_router = APIRouter()
api_router.include_router(speech.router, prefix="", tags=["Emotion"])
