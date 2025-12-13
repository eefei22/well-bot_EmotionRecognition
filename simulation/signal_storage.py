"""
Signal Storage

Manages JSONL file storage for simulation signals (SER, FER, Vitals).
Provides thread-safe read/write operations.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .config import SER_SIGNALS_FILE, FER_SIGNALS_FILE, VITALS_SIGNALS_FILE
from app.models import ModelSignal

logger = logging.getLogger(__name__)


class SignalStorage:
    """
    Manages JSONL file storage for simulation signals.
    Thread-safe operations for reading and writing signals.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # File paths for each modality
    _file_paths = {
        "ser": SER_SIGNALS_FILE,
        "fer": FER_SIGNALS_FILE,
        "vitals": VITALS_SIGNALS_FILE
    }
    
    # Locks for each modality file
    _file_locks = {
        "ser": threading.Lock(),
        "fer": threading.Lock(),
        "vitals": threading.Lock()
    }
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SignalStorage, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize signal storage."""
        if self._initialized:
            return
        
        # Ensure all files exist (create empty files if needed)
        for modality, file_path in self._file_paths.items():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                file_path.touch()
                logger.info(f"Created signal file: {file_path}")
        
        self._initialized = True
        logger.info("SignalStorage initialized")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def _get_file_path(self, modality: str) -> Path:
        """
        Get file path for a modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            
        Returns:
            Path to the JSONL file
        """
        modality_lower = modality.lower()
        if modality_lower not in self._file_paths:
            raise ValueError(f"Unknown modality: {modality}")
        return self._file_paths[modality_lower]
    
    def _get_file_lock(self, modality: str) -> threading.Lock:
        """Get file lock for a modality."""
        modality_lower = modality.lower()
        if modality_lower not in self._file_locks:
            raise ValueError(f"Unknown modality: {modality}")
        return self._file_locks[modality_lower]
    
    def write_signal(self, modality: str, signal: ModelSignal) -> None:
        """
        Append a signal to the JSONL file for the given modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            signal: ModelSignal object to write
        """
        file_path = self._get_file_path(modality)
        file_lock = self._get_file_lock(modality)
        
        with file_lock:
            try:
                # Convert ModelSignal to dict
                signal_dict = signal.dict()
                
                # Append to JSONL file
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(signal_dict) + "\n")
                
                logger.debug(f"Wrote signal to {modality} file: {signal_dict}")
            except Exception as e:
                logger.error(f"Error writing signal to {modality} file: {e}", exc_info=True)
                raise
    
    def read_signals_in_window(
        self,
        modality: str,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[ModelSignal]:
        """
        Read signals from JSONL file within a time window.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            user_id: User ID to filter by
            start_time: Start of time window (inclusive)
            end_time: End of time window (inclusive)
            
        Returns:
            List of ModelSignal objects within the window
        """
        file_path = self._get_file_path(modality)
        file_lock = self._get_file_lock(modality)
        
        signals = []
        
        with file_lock:
            try:
                if not file_path.exists():
                    logger.debug(f"Signal file does not exist: {file_path}")
                    return signals
                
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            signal_dict = json.loads(line)
                            
                            # Filter by user_id
                            if signal_dict.get("user_id") != user_id:
                                continue
                            
                            # Parse timestamp
                            signal_timestamp = datetime.fromisoformat(
                                signal_dict["timestamp"].replace("Z", "+00:00")
                            )
                            
                            # Filter by time window
                            if start_time <= signal_timestamp <= end_time:
                                signal = ModelSignal(**signal_dict)
                                signals.append(signal)
                        
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            logger.warning(f"Error parsing signal line: {e}")
                            continue
                
                logger.debug(
                    f"Read {len(signals)} signals from {modality} file "
                    f"for user {user_id} in window [{start_time}, {end_time}]"
                )
            
            except Exception as e:
                logger.error(f"Error reading signals from {modality} file: {e}", exc_info=True)
                raise
        
        return signals
    
    def clear_signals(self, modality: str) -> None:
        """
        Clear all signals from the JSONL file for the given modality.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
        """
        file_path = self._get_file_path(modality)
        file_lock = self._get_file_lock(modality)
        
        with file_lock:
            try:
                # Truncate file
                file_path.write_text("")
                logger.info(f"Cleared all signals from {modality} file")
            except Exception as e:
                logger.error(f"Error clearing signals from {modality} file: {e}", exc_info=True)
                raise
    
    def get_signal_count(self, modality: str) -> int:
        """
        Get the count of signals in the JSONL file.
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            
        Returns:
            Number of signals in the file
        """
        file_path = self._get_file_path(modality)
        file_lock = self._get_file_lock(modality)
        
        count = 0
        
        with file_lock:
            try:
                if not file_path.exists():
                    return 0
                
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            count += 1
            
            except Exception as e:
                logger.error(f"Error counting signals in {modality} file: {e}", exc_info=True)
        
        return count
    
    def get_all_signals(self, modality: str, limit: Optional[int] = None) -> List[ModelSignal]:
        """
        Get all signals from the JSONL file (for dashboard).
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            limit: Optional limit on number of signals to return (most recent)
            
        Returns:
            List of ModelSignal objects
        """
        file_path = self._get_file_path(modality)
        file_lock = self._get_file_lock(modality)
        
        signals = []
        
        with file_lock:
            try:
                if not file_path.exists():
                    return signals
                
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            signal_dict = json.loads(line)
                            signal = ModelSignal(**signal_dict)
                            signals.append(signal)
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(f"Error parsing signal line: {e}")
                            continue
                
                # Return most recent signals if limit is specified
                if limit is not None and limit > 0:
                    signals = signals[-limit:]
            
            except Exception as e:
                logger.error(f"Error reading all signals from {modality} file: {e}", exc_info=True)
        
        return signals
    
    def get_file_status(self, modality: str) -> dict:
        """
        Get file status information (exists, size, last modified).
        
        Args:
            modality: Modality name ("ser", "fer", "vitals")
            
        Returns:
            Dictionary with file status information
        """
        file_path = self._get_file_path(modality)
        
        try:
            if not file_path.exists():
                return {
                    "exists": False,
                    "size": 0,
                    "last_modified": None
                }
            
            stat = file_path.stat()
            return {
                "exists": True,
                "size": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting file status for {modality}: {e}", exc_info=True)
            return {
                "exists": False,
                "size": 0,
                "last_modified": None,
                "error": str(e)
            }


