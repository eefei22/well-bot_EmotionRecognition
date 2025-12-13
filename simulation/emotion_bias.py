"""
Emotion Bias Manager

Manages emotion bias state for signal generation.
Each modality (SER, FER, Vitals) can have an independent bias toward a specific emotion.
"""

import threading
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Valid emotion options
VALID_EMOTIONS = ["Happy", "Sad", "Fear", "Angry"]


class EmotionBiasManager:
    """
    Singleton class for managing emotion bias state per modality.
    Bias is stored in-memory and resets on service restart.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EmotionBiasManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize emotion bias manager."""
        if self._initialized:
            return
        
        # Initialize bias state: None means no bias (equal probability)
        self._biases: Dict[str, Optional[str]] = {
            "ser": None,
            "fer": None,
            "vitals": None
        }
        self._lock = threading.Lock()
        self._initialized = True
        logger.info("EmotionBiasManager initialized (all biases: None)")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def get_bias(self, modality: str) -> Optional[str]:
        """
        Get bias for a specific modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            
        Returns:
            Bias emotion ("Happy", "Sad", "Fear", "Angry") or None if no bias
        """
        modality = modality.lower()
        with self._lock:
            return self._biases.get(modality, None)
    
    def set_bias(self, modality: str, emotion: Optional[str]) -> None:
        """
        Set bias for a specific modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            emotion: Emotion to bias toward ("Happy", "Sad", "Fear", "Angry") or None to clear bias
            
        Raises:
            ValueError: If emotion is not valid
        """
        modality = modality.lower()
        
        # Validate modality
        if modality not in ["ser", "fer", "vitals"]:
            raise ValueError(f"Invalid modality: {modality}. Must be 'ser', 'fer', or 'vitals'")
        
        # Validate emotion
        if emotion is not None and emotion not in VALID_EMOTIONS:
            raise ValueError(f"Invalid emotion: {emotion}. Must be one of {VALID_EMOTIONS} or None")
        
        with self._lock:
            old_bias = self._biases.get(modality)
            self._biases[modality] = emotion
            logger.info(f"Emotion bias for {modality} changed: {old_bias} -> {emotion}")
    
    def get_all_biases(self) -> Dict[str, Optional[str]]:
        """
        Get all biases for all modalities.
        
        Returns:
            Dictionary mapping modality to bias emotion (or None)
        """
        with self._lock:
            return self._biases.copy()

