"""
Session Manager

In-memory session management and chunk result storage.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from threading import Lock
from collections import defaultdict

from app.models import ChunkResult
from app.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages sessions and chunk results in memory.
    
    Structure:
    _sessions[user_id][session_id] = List[ChunkResult]
    _session_metadata[user_id][session_id] = {
        'start_time': datetime,
        'last_chunk_time': datetime
    }
    """
    
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        """Initialize SessionManager (singleton pattern)."""
        # user_id -> session_id -> List[ChunkResult]
        self._sessions: Dict[str, Dict[str, List[ChunkResult]]] = defaultdict(dict)
        
        # user_id -> session_id -> metadata
        self._session_metadata: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        
        # Per-user locks for thread safety
        self._user_locks: Dict[str, Lock] = defaultdict(Lock)
        
        # Global lock for session creation/deletion
        self._global_lock = Lock()
        
        self.session_gap_threshold = timedelta(seconds=settings.SESSION_GAP_THRESHOLD_SECONDS)
        
        logger.info(f"SessionManager initialized (gap threshold: {settings.SESSION_GAP_THRESHOLD_SECONDS}s)")
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance of SessionManager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def add_result(self, user_id: str, result: ChunkResult) -> str:
        """
        Add a chunk result to the appropriate session.
        
        Args:
            user_id: User identifier
            result: ChunkResult with timestamp and analysis data
        
        Returns:
            session_id: The session ID where the result was added
        """
        user_lock = self._user_locks[user_id]
        
        with user_lock:
            # Detect or create session
            session_id = self._detect_or_create_session(user_id, result.timestamp)
            
            # Add result to session
            if session_id not in self._sessions[user_id]:
                self._sessions[user_id][session_id] = []
                self._session_metadata[user_id][session_id] = {
                    'start_time': result.timestamp,
                    'last_chunk_time': result.timestamp
                }
            
            self._sessions[user_id][session_id].append(result)
            self._session_metadata[user_id][session_id]['last_chunk_time'] = result.timestamp
            
            logger.debug(
                f"Added result to session {session_id} for user {user_id} "
                f"(total chunks: {len(self._sessions[user_id][session_id])})"
            )
            
            return session_id
    
    def _detect_or_create_session(self, user_id: str, timestamp: datetime) -> str:
        """
        Detect existing session or create new one based on timestamp gap.
        
        Args:
            user_id: User identifier
            timestamp: Timestamp of the new chunk
        
        Returns:
            session_id: Session identifier
        """
        # If no sessions exist for user, create first session
        if not self._sessions[user_id]:
            session_id = f"{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            logger.debug(f"Created first session {session_id} for user {user_id}")
            return session_id
        
        # Check all existing sessions for this user
        # Find the most recent session
        most_recent_session = None
        most_recent_time = None
        
        for session_id, metadata in self._session_metadata[user_id].items():
            last_chunk_time = metadata['last_chunk_time']
            if most_recent_time is None or last_chunk_time > most_recent_time:
                most_recent_time = last_chunk_time
                most_recent_session = session_id
        
        # Check if gap is large enough for new session
        if most_recent_session and most_recent_time:
            gap = timestamp - most_recent_time
            if gap > self.session_gap_threshold:
                # Create new session
                session_id = f"{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
                logger.debug(
                    f"Gap of {gap.total_seconds():.1f}s detected, "
                    f"creating new session {session_id} for user {user_id}"
                )
                return session_id
            else:
                # Use existing session
                logger.debug(
                    f"Gap of {gap.total_seconds():.1f}s is within threshold, "
                    f"using existing session {most_recent_session} for user {user_id}"
                )
                return most_recent_session
        
        # Fallback: create new session
        session_id = f"{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        logger.debug(f"Fallback: created session {session_id} for user {user_id}")
        return session_id
    
    def get_results_in_window(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[ChunkResult]:
        """
        Get all chunk results for a user within the specified time window.
        
        Args:
            user_id: User identifier
            start_time: Start of time window (inclusive)
            end_time: End of time window (inclusive)
        
        Returns:
            List of ChunkResult objects within the window
        """
        user_lock = self._user_locks[user_id]
        results = []
        
        with user_lock:
            if user_id not in self._sessions:
                logger.debug(f"No sessions found for user {user_id}")
                return results
            
            # Iterate through all sessions for this user
            for session_id, chunk_results in self._sessions[user_id].items():
                for result in chunk_results:
                    # Check if result timestamp is within window
                    if start_time <= result.timestamp <= end_time:
                        results.append(result)
            
            logger.debug(
                f"Found {len(results)} results for user {user_id} "
                f"in window [{start_time}, {end_time}]"
            )
        
        return results
    
    def get_all_sessions(self, user_id: str) -> Dict[str, List[ChunkResult]]:
        """
        Get all sessions for a user (for debugging/admin purposes).
        
        Args:
            user_id: User identifier
        
        Returns:
            Dictionary mapping session_id to list of ChunkResult objects
        """
        user_lock = self._user_locks[user_id]
        
        with user_lock:
            if user_id not in self._sessions:
                return {}
            
            # Return a copy to prevent external modification
            return {
                session_id: results.copy()
                for session_id, results in self._sessions[user_id].items()
            }
    
    def cleanup_old_sessions(self, user_id: str, before_timestamp: datetime):
        """
        Remove sessions and results older than the specified timestamp.
        
        Args:
            user_id: User identifier
            before_timestamp: Remove sessions with last chunk before this timestamp
        """
        user_lock = self._user_locks[user_id]
        
        with user_lock:
            if user_id not in self._sessions:
                return
            
            sessions_to_remove = []
            
            for session_id, metadata in self._session_metadata[user_id].items():
                if metadata['last_chunk_time'] < before_timestamp:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                chunk_count = len(self._sessions[user_id][session_id])
                del self._sessions[user_id][session_id]
                del self._session_metadata[user_id][session_id]
                logger.debug(
                    f"Cleaned up session {session_id} for user {user_id} "
                    f"({chunk_count} chunks removed)"
                )
    
    def get_active_sessions_in_window(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> Dict[str, Dict[str, List[ChunkResult]]]:
        """
        Get all active sessions (across all users) that have results within the time window.
        
        Args:
            window_start: Start of aggregation window
            window_end: End of aggregation window
        
        Returns:
            Dictionary: user_id -> session_id -> List[ChunkResult]
        """
        active_sessions = {}
        
        with self._global_lock:
            # Get all user IDs
            all_user_ids = list(self._sessions.keys())
        
        for user_id in all_user_ids:
            user_lock = self._user_locks[user_id]
            
            with user_lock:
                if user_id not in self._sessions:
                    continue
                
                for session_id, chunk_results in self._sessions[user_id].items():
                    # Check if any result in this session is within the window
                    session_results_in_window = [
                        result for result in chunk_results
                        if window_start <= result.timestamp <= window_end
                    ]
                    
                    if session_results_in_window:
                        if user_id not in active_sessions:
                            active_sessions[user_id] = {}
                        active_sessions[user_id][session_id] = session_results_in_window
        
        return active_sessions
    
    def clear_user_sessions(self, user_id: str):
        """
        Clear all sessions for a specific user (for testing/cleanup).
        
        Args:
            user_id: User identifier
        """
        user_lock = self._user_locks[user_id]
        
        with user_lock:
            if user_id in self._sessions:
                session_count = len(self._sessions[user_id])
                del self._sessions[user_id]
                del self._session_metadata[user_id]
                logger.info(f"Cleared {session_count} sessions for user {user_id}")
