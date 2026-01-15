"""
SER Service Configuration

SER-specific configuration settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """SER service configuration settings."""
    
    # Aggregation and session configuration
    AGGREGATION_WINDOW_SECONDS: int = 300  # 5 minutes default
    SESSION_GAP_THRESHOLD_SECONDS: int = 60  # 1 minute gap = new session
    FUSION_SERVICE_URL: Optional[str] = None  # Optional, for future auto-send to fusion
    
    # Queue processing configuration
    PROCESSING_TIMEOUT_SECONDS: int = 300  # 5 minutes timeout for processing a single chunk
    
    # Result logging
    RESULTS_LOG_DIR: str = "data/ser_results"  # Directory for result log files
    RESULTS_LOG_ENABLED: bool = True  # Enable/disable result logging to file
    
    # FunASR Configuration
    FUNASR_HUB: str = "hf"  # "hf" for HuggingFace, "ms" for ModelScope
    EMOTION2VEC_MODEL: str = "iic/emotion2vec_plus_base"  # emotion2vec+ base model
    EMOTION_FORMAT: str = "7class"  # "7class" or "9class" - emotion label format
    
    # Paraformer ASR Models (language-specific)
    # Note: Verify actual model names from FunASR model zoo (HuggingFace or ModelScope)
    # Common Paraformer models: paraformer-zh, paraformer-en-v1, etc.
    # For now using paraformer-zh as default (supports multiple languages)
    # TODO: Verify and update with actual language-specific model names
    ASR_MODEL_EN: str = "paraformer-zh"  # English Paraformer (verify actual name from FunASR)
    ASR_MODEL_ZH: str = "paraformer-zh"  # Chinese Paraformer
    ASR_MODEL_MS: str = "paraformer-zh"  # Malay Paraformer (use Chinese as fallback if unavailable)

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env that aren't defined here


settings = Settings()
