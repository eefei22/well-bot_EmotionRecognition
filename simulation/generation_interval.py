"""
Generation Interval Manager

Manages the signal generation interval setting for the simulation module.
Controls how frequently signals are generated when demo mode is enabled.
"""

import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default interval in seconds
DEFAULT_INTERVAL = 30

# Min and max allowed intervals (in seconds)
MIN_INTERVAL = 5
MAX_INTERVAL = 300  # 5 minutes max


class GenerationIntervalManager:
    """
    Singleton class for managing signal generation interval.
    Interval is stored in-memory and resets to default on service restart.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GenerationIntervalManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize generation interval manager."""
        if self._initialized:
            return
        
        self._interval = DEFAULT_INTERVAL
        self._lock = threading.Lock()
        self._initialized = True
        logger.info(f"GenerationIntervalManager initialized (interval: {DEFAULT_INTERVAL}s)")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def get_interval(self) -> int:
        """
        Get current generation interval.
        
        Returns:
            Interval in seconds
        """
        with self._lock:
            return self._interval
    
    def set_interval(self, interval: int) -> None:
        """
        Set generation interval.
        
        Args:
            interval: Interval in seconds (must be between MIN_INTERVAL and MAX_INTERVAL)
            
        Raises:
            ValueError: If interval is out of valid range
        """
        if interval < MIN_INTERVAL or interval > MAX_INTERVAL:
            raise ValueError(
                f"Interval must be between {MIN_INTERVAL} and {MAX_INTERVAL} seconds. "
                f"Got: {interval}"
            )
        
        with self._lock:
            old_interval = self._interval
            self._interval = interval
            logger.info(f"Generation interval changed: {old_interval}s -> {interval}s")
    
    def get_status(self) -> dict:
        """
        Get current interval status.
        
        Returns:
            Dictionary with 'interval' key and min/max bounds
        """
        with self._lock:
            return {
                "interval": self._interval,
                "min_interval": MIN_INTERVAL,
                "max_interval": MAX_INTERVAL,
                "default_interval": DEFAULT_INTERVAL
            }

