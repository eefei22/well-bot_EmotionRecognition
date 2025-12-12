"""
Aggregator for SER Service

Aggregates chunk results over time windows (default: 5 minutes),
calculates averages, and writes to log files.
"""

import logging
import json
import os
import threading
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from app.session_manager import SessionManager
from app.models import ChunkResult, AggregatedResult
from app.config import settings

logger = logging.getLogger(__name__)


class Aggregator:
    """
    Aggregates chunk results and writes to log files.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize Aggregator (singleton pattern)."""
        self.session_manager = SessionManager.get_instance()
        self.aggregation_window = timedelta(seconds=settings.AGGREGATION_WINDOW_SECONDS)
        self.log_dir = settings.AGGREGATION_LOG_DIR
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.running = False
        self._running_lock = threading.Lock()
        self.timer_thread: Optional[threading.Thread] = None
        
        logger.info(
            f"Aggregator initialized "
            f"(window: {settings.AGGREGATION_WINDOW_SECONDS}s, log_dir: {self.log_dir})"
        )
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance of Aggregator."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def start_periodic_aggregation(self):
        """Start periodic aggregation timer."""
        with self._running_lock:
            if self.running:
                logger.warning("Aggregator periodic timer already running")
                return
            
            self.running = True
            self.timer_thread = threading.Thread(
                target=self._periodic_loop,
                daemon=True,
                name="SER-Aggregator"
            )
            self.timer_thread.start()
            logger.info("Aggregator periodic timer started")
    
    def stop_periodic_aggregation(self):
        """Stop periodic aggregation timer."""
        with self._running_lock:
            if not self.running:
                return
            
            self.running = False
        
        # Wait for thread to finish
        if self.timer_thread and self.timer_thread.is_alive():
            logger.info("Waiting for Aggregator timer thread to finish...")
            self.timer_thread.join(timeout=5.0)
            if self.timer_thread.is_alive():
                logger.warning("Aggregator timer thread did not finish within timeout")
            else:
                logger.info("Aggregator timer thread finished")
        
        self.timer_thread = None
    
    def _periodic_loop(self):
        """Periodic loop that runs aggregation every N seconds."""
        logger.info("Aggregator periodic loop started")
        
        # Wait for initial window before first aggregation
        time.sleep(self.aggregation_window.total_seconds())
        
        while True:
            with self._running_lock:
                if not self.running:
                    break
            
            try:
                # Run aggregation
                self.run_aggregation()
            except Exception as e:
                logger.error(f"Error in periodic aggregation: {e}", exc_info=True)
            
            # Wait for next aggregation window
            time.sleep(self.aggregation_window.total_seconds())
        
        logger.info("Aggregator periodic loop ended")
    
    def run_aggregation(self):
        """
        Run aggregation for all active sessions.
        Aggregates results from the last aggregation window.
        """
        aggregation_time = datetime.now()
        window_end = aggregation_time
        window_start = window_end - self.aggregation_window
        
        logger.info(
            f"Running aggregation for window [{window_start}, {window_end}]"
        )
        
        # Get all active sessions with results in this window
        active_sessions = self.session_manager.get_active_sessions_in_window(
            window_start, window_end
        )
        
        if not active_sessions:
            logger.debug("No active sessions found in aggregation window")
            return
        
        aggregated_count = 0
        
        # Aggregate each session
        for user_id, sessions in active_sessions.items():
            for session_id, chunk_results in sessions.items():
                try:
                    aggregated_result = self._aggregate_session(
                        user_id=user_id,
                        session_id=session_id,
                        chunk_results=chunk_results,
                        window_start=window_start,
                        window_end=window_end
                    )
                    
                    # Write to log file
                    self._write_to_log(aggregated_result)
                    
                    aggregated_count += 1
                    
                except Exception as e:
                    logger.error(
                        f"Failed to aggregate session {session_id} for user {user_id}: {e}",
                        exc_info=True
                    )
        
        logger.info(
            f"Aggregation completed: {aggregated_count} sessions aggregated "
            f"for window [{window_start}, {window_end}]"
        )
        
        # Clean up old sessions (older than 2x aggregation window)
        cleanup_before = window_end - (2 * self.aggregation_window)
        for user_id in active_sessions.keys():
            self.session_manager.cleanup_old_sessions(user_id, cleanup_before)
    
    def _aggregate_session(
        self,
        user_id: str,
        session_id: str,
        chunk_results: List[ChunkResult],
        window_start: datetime,
        window_end: datetime
    ) -> AggregatedResult:
        """
        Aggregate chunk results for a session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            chunk_results: List of ChunkResult objects to aggregate
            window_start: Start of aggregation window
            window_end: End of aggregation window
        
        Returns:
            AggregatedResult with averaged values
        """
        if not chunk_results:
            raise ValueError(f"No chunk results to aggregate for session {session_id}")
        
        # Group by emotion label and calculate average confidence per emotion
        emotion_confidences = defaultdict(list)
        sentiment_confidences = defaultdict(list)
        
        for result in chunk_results:
            # Collect emotion confidences
            emotion_confidences[result.emotion].append(result.emotion_confidence)
            
            # Collect sentiment confidences (if available)
            if result.sentiment and result.sentiment_confidence is not None:
                sentiment_confidences[result.sentiment].append(result.sentiment_confidence)
        
        # Calculate average confidence per emotion
        emotion_avg_confidences = {
            emotion: sum(confs) / len(confs)
            for emotion, confs in emotion_confidences.items()
        }
        
        # Select emotion with highest average confidence
        if emotion_avg_confidences:
            best_emotion = max(emotion_avg_confidences.items(), key=lambda x: x[1])
            aggregated_emotion = best_emotion[0]
            aggregated_emotion_confidence = best_emotion[1]
        else:
            # Fallback if no emotions found
            aggregated_emotion = "unknown"
            aggregated_emotion_confidence = 0.0
        
        # Calculate average sentiment confidence (for the most common sentiment)
        aggregated_sentiment = None
        aggregated_sentiment_confidence = None
        
        if sentiment_confidences:
            # Use sentiment with most occurrences
            sentiment_counts = {
                sentiment: len(confs)
                for sentiment, confs in sentiment_confidences.items()
            }
            most_common_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])[0]
            aggregated_sentiment = most_common_sentiment
            aggregated_sentiment_confidence = sum(sentiment_confidences[most_common_sentiment]) / len(
                sentiment_confidences[most_common_sentiment]
            )
        
        # Create aggregated result
        aggregated_result = AggregatedResult(
            timestamp=window_end,
            user_id=user_id,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            chunk_count=len(chunk_results),
            emotion=aggregated_emotion,
            emotion_confidence=aggregated_emotion_confidence,
            sentiment=aggregated_sentiment,
            sentiment_confidence=aggregated_sentiment_confidence
        )
        
        logger.debug(
            f"Aggregated {len(chunk_results)} chunks for session {session_id}: "
            f"emotion={aggregated_emotion}, confidence={aggregated_emotion_confidence:.3f}"
        )
        
        return aggregated_result
    
    def _write_to_log(self, aggregated_result: AggregatedResult):
        """
        Write aggregated result to JSON log file.
        
        Args:
            aggregated_result: AggregatedResult to write
        """
        # Create log entry
        log_entry = {
            "timestamp": aggregated_result.timestamp.isoformat(),
            "user_id": aggregated_result.user_id,
            "session_id": aggregated_result.session_id,
            "window_start": aggregated_result.window_start.isoformat(),
            "window_end": aggregated_result.window_end.isoformat(),
            "chunk_count": aggregated_result.chunk_count,
            "aggregated_result": {
                "emotion": aggregated_result.emotion,
                "emotion_confidence": aggregated_result.emotion_confidence,
                "sentiment": aggregated_result.sentiment,
                "sentiment_confidence": aggregated_result.sentiment_confidence
            }
        }
        
        # Write to JSON Lines file (one entry per line)
        log_file = os.path.join(self.log_dir, "aggregation_log.jsonl")
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                json.dump(log_entry, f, ensure_ascii=False)
                f.write("\n")
            
            logger.debug(f"Written aggregation log entry to {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to write aggregation log entry: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """Check if periodic aggregation is running."""
        with self._running_lock:
            return self.running
