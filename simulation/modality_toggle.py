"""
Modality Generation Toggle Manager

Manages per-modality generation toggles (SER, FER, Vitals).
Allows independent control of signal generation for each modality.
"""

import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ModalityToggleManager:
    """
    Manages per-modality generation toggles.
    Thread-safe singleton pattern.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModalityToggleManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize modality toggle manager."""
        if self._initialized:
            return
        
        # Default: all modalities enabled
        self._modality_states: Dict[str, bool] = {
            "ser": True,
            "fer": True,
            "vitals": True
        }
        self._state_lock = threading.Lock()
        
        self._initialized = True
        logger.info("ModalityToggleManager initialized (all modalities enabled by default)")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def is_enabled(self, modality: str) -> bool:
        """
        Check if generation is enabled for a modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
        
        Returns:
            True if enabled, False otherwise
        """
        modality_lower = modality.lower()
        with self._state_lock:
            return self._modality_states.get(modality_lower, False)
    
    def set_enabled(self, modality: str, enabled: bool) -> None:
        """
        Set generation enabled/disabled for a modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            enabled: True to enable, False to disable
        """
        modality_lower = modality.lower()
        if modality_lower not in ["ser", "fer", "vitals"]:
            raise ValueError(f"Invalid modality: {modality}. Must be 'ser', 'fer', or 'vitals'")
        
        with self._state_lock:
            old_state = self._modality_states.get(modality_lower, False)
            self._modality_states[modality_lower] = enabled
            logger.info(f"Modality '{modality_lower}' generation {'enabled' if enabled else 'disabled'} (was: {'enabled' if old_state else 'disabled'})")
    
    def get_all_states(self) -> Dict[str, bool]:
        """
        Get all modality states.
        
        Returns:
            Dictionary mapping modality names to enabled states
        """
        with self._state_lock:
            return self._modality_states.copy()
    
    def get_status(self) -> Dict[str, any]:
        """
        Get status dictionary for API responses.
        
        Returns:
            Dictionary with modality states
        """
        with self._state_lock:
            return {
                "ser": self._modality_states.get("ser", False),
                "fer": self._modality_states.get("fer", False),
                "vitals": self._modality_states.get("vitals", False)
            }

