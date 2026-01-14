"""
SER Result Logger

Manages in-memory storage for SER processing results.
Provides thread-safe read/write operations for aggregated and individual results.
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import get_malaysia_timezone - use lazy import to avoid circular dependencies
def _get_malaysia_timezone():
    """Lazy import to avoid circular dependencies."""
    from app.database import get_malaysia_timezone
    return get_malaysia_timezone()

logger = logging.getLogger(__name__)

# In-memory storage for SER results
_aggregated_results = deque(maxlen=1000)  # Store up to 1000 aggregated results
_individual_results = deque(maxlen=500)   # Store up to 500 individual results

# Thread locks for safe concurrent access
_aggregated_lock = threading.Lock()
_individual_lock = threading.Lock()


def log_aggregated_result(
    user_id: str,
    session_id: str,
    timestamp: str,
    window_start: str,
    window_end: str,
    chunk_count: int,
    aggregated_result: Dict[str, Any]
) -> None:
    """
    Log an aggregated SER result to in-memory storage.

    Args:
        user_id: User identifier
        session_id: Session identifier
        timestamp: Timestamp when aggregation occurred (ISO format)
        window_start: Start of aggregation window (ISO format)
        window_end: End of aggregation window (ISO format)
        chunk_count: Number of chunks aggregated
        aggregated_result: Dictionary with emotion, sentiment, confidence data
    """
    try:
        log_entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "session_id": session_id,
            "window_start": window_start,
            "window_end": window_end,
            "chunk_count": chunk_count,
            "aggregated_result": aggregated_result
        }

        with _aggregated_lock:
            _aggregated_results.append(log_entry)

        logger.debug(f"Logged aggregated result for user {user_id}, session {session_id}")

    except Exception as e:
        logger.error(f"Error logging aggregated result: {e}", exc_info=True)


def log_individual_result(
    user_id: str,
    timestamp: str,
    result: Dict[str, Any]
) -> None:
    """
    Log an individual SER processing result to in-memory storage.

    Args:
        user_id: User identifier
        timestamp: Timestamp when chunk was captured (ISO format)
        result: Result dictionary with emotion, transcript, etc.
    """
    try:
        log_entry = {
            "user_id": user_id,
            "timestamp": timestamp,
            "processed_at": datetime.now(_get_malaysia_timezone()).isoformat(),
            **result
        }

        with _individual_lock:
            _individual_results.append(log_entry)

        logger.debug(f"Logged individual result for user {user_id}")

    except Exception as e:
        logger.error(f"Error logging individual result: {e}", exc_info=True)


def read_aggregated_results(
    limit: int = 100,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Read aggregated results from in-memory storage.

    Args:
        limit: Maximum number of entries to return
        user_id: Optional filter by user_id

    Returns:
        List of aggregated result dictionaries (newest first)
    """
    try:
        with _aggregated_lock:
            # Convert deque to list (deque maintains insertion order, newest last)
            # We want newest first, so reverse it
            all_entries = list(_aggregated_results)
            all_entries.reverse()  # Newest first

        # Filter by user_id if provided
        if user_id:
            all_entries = [entry for entry in all_entries if entry.get("user_id") == user_id]

        # Return last N entries (already newest first)
        return all_entries[:limit]

    except Exception as e:
        logger.error(f"Error reading aggregated results: {e}", exc_info=True)
        return []


def read_individual_results(
    limit: int = 100,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Read individual results from in-memory storage.

    Args:
        limit: Maximum number of entries to return
        user_id: Optional filter by user_id

    Returns:
        List of individual result dictionaries (newest first)
    """
    try:
        with _individual_lock:
            # Convert deque to list (deque maintains insertion order, newest last)
            # We want newest first, so reverse it
            all_entries = list(_individual_results)
            all_entries.reverse()  # Newest first

        # Filter by user_id if provided
        if user_id:
            all_entries = [entry for entry in all_entries if entry.get("user_id") == user_id]

        # Return last N entries (already newest first)
        return all_entries[:limit]

    except Exception as e:
        logger.error(f"Error reading individual results: {e}", exc_info=True)
        return []


def clear_aggregated_results() -> None:
    """Clear all aggregated results from memory."""
    with _aggregated_lock:
        _aggregated_results.clear()
    logger.info("Cleared all aggregated results")


def clear_individual_results() -> None:
    """Clear all individual results from memory."""
    with _individual_lock:
        _individual_results.clear()
    logger.info("Cleared all individual results")


def get_aggregated_count() -> int:
    """Get the current number of aggregated results in memory."""
    with _aggregated_lock:
        return len(_aggregated_results)


def get_individual_count() -> int:
    """Get the current number of individual results in memory."""
    with _individual_lock:
        return len(_individual_results)
