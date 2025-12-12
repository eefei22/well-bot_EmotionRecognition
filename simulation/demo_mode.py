"""
Demo Mode Manager

Manages the demo mode state for the simulation module.
Demo mode controls whether fusion uses simulation endpoints and whether
signal generator should generate signals.
"""

import threading
import logging

logger = logging.getLogger(__name__)


class DemoModeManager:
    """
    Singleton class for managing demo mode state.
    Demo mode is stored in-memory and resets on service restart.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DemoModeManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize demo mode manager."""
        if self._initialized:
            return
        
        self._enabled = False
        self._lock = threading.Lock()
        self._initialized = True
        logger.info("DemoModeManager initialized (demo mode: OFF)")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def is_enabled(self) -> bool:
        """
        Check if demo mode is enabled.
        
        Returns:
            True if demo mode is enabled, False otherwise
        """
        with self._lock:
            return self._enabled
    
    def set_enabled(self, enabled: bool) -> None:
        """
        Set demo mode state.
        
        Args:
            enabled: True to enable demo mode, False to disable
        """
        with self._lock:
            old_state = self._enabled
            self._enabled = enabled
            logger.info(f"Demo mode changed: {old_state} -> {enabled}")
    
    def get_status(self) -> dict:
        """
        Get current demo mode status.
        
        Returns:
            Dictionary with 'enabled' key
        """
        with self._lock:
            return {"enabled": self._enabled}

