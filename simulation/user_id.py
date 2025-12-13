"""
User ID Manager

Manages the user UUID setting for the simulation module.
Controls which user receives generated signals.
"""

import threading
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# Default user ID from environment variable or fallback
DEFAULT_USER_ID = os.getenv("DEV_USER_ID", "96975f52-5b05-4eb1-bfa5-530485112518")


class UserIdManager:
    """
    Singleton class for managing user UUID.
    UUID is stored in-memory and resets to default on service restart.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(UserIdManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize user ID manager."""
        if self._initialized:
            return
        
        self._user_id = DEFAULT_USER_ID
        self._lock = threading.Lock()
        self._initialized = True
        logger.info(f"UserIdManager initialized (user_id: {DEFAULT_USER_ID})")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def get_user_id(self) -> str:
        """
        Get current user UUID.
        
        Returns:
            User UUID string
        """
        with self._lock:
            return self._user_id
    
    def set_user_id(self, user_id: str) -> None:
        """
        Set user UUID.
        
        Args:
            user_id: User UUID string (must be valid UUID format)
            
        Raises:
            ValueError: If user_id is not a valid UUID format
        """
        # Validate UUID format
        try:
            uuid.UUID(user_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid UUID format: {user_id}. Must be a valid UUID.")
        
        with self._lock:
            old_user_id = self._user_id
            self._user_id = user_id
            logger.info(f"User ID changed: {old_user_id} -> {user_id}")
    
    def get_status(self) -> dict:
        """
        Get current user ID status.
        
        Returns:
            Dictionary with 'user_id' key
        """
        with self._lock:
            return {
                "user_id": self._user_id
            }

