"""
Aggregation Interval Manager

Manages the aggregation window interval setting for the SER service.
Controls how frequently aggregation runs (time window for aggregating results).
"""

import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default interval in seconds (5 minutes)
DEFAULT_INTERVAL = 300

# Min and max allowed intervals (in seconds)
MIN_INTERVAL = 60  # 1 minute minimum
MAX_INTERVAL = 3600  # 1 hour maximum


class AggregationIntervalManager:
    """
    Singleton class for managing aggregation interval.
    Interval is stored in-memory and resets to default on service restart.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AggregationIntervalManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize aggregation interval manager."""
        if self._initialized:
            return
        
        self._interval = DEFAULT_INTERVAL
        self._lock = threading.Lock()
        self._initialized = True
        logger.info(f"AggregationIntervalManager initialized (interval: {DEFAULT_INTERVAL}s)")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def get_interval(self) -> int:
        """
        Get current aggregation interval.
        
        Returns:
            Interval in seconds
        """
        with self._lock:
            return self._interval
    
    def set_interval(self, interval: int) -> None:
        """
        Set aggregation interval.
        
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
            logger.info(f"Aggregation interval changed: {old_interval}s -> {interval}s")
    
    def get_status(self) -> dict:
        """
        Get current interval status.
        
        Returns:
            Dictionary with 'interval_seconds' key and min/max bounds
        """
        with self._lock:
            return {
                "interval_seconds": self._interval,
                "min_interval": MIN_INTERVAL,
                "max_interval": MAX_INTERVAL,
                "default_interval": DEFAULT_INTERVAL
            }

