"""
Queue Manager

Asynchronous processing queue with background worker thread.
"""

import logging
import threading
import os
import time
import json
from queue import Queue, Empty
from typing import Tuple, Optional, List, Dict
from datetime import datetime

from app.processing_pipeline import analyze_full
from app.session_manager import SessionManager
from app.models import ChunkResult
from app.config import settings

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Manages queue and background processing of audio chunks.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize QueueManager (singleton pattern)."""
        # Queue items: (user_id, audio_file_path, timestamp, filename)
        self.queue: Queue[Tuple[str, str, datetime, Optional[str]]] = Queue()
        
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        self._running_lock = threading.Lock()
        
        # Track queue items for dashboard (metadata only, not the actual file)
        self._queue_items: List[Dict] = []  # List of {user_id, timestamp, filename}
        self._queue_lock = threading.Lock()
        
        # Track currently processing item
        self._processing_item: Optional[Dict] = None  # {user_id, started_at, result}
        self._processing_lock = threading.Lock()
        
        # Track recent results
        self._recent_results: List[Dict] = []  # List of recent ChunkResult dicts
        self._results_lock = threading.Lock()
        self._max_recent_results = 100
        
        self.session_manager = SessionManager.get_instance()
        
        # Result log file setup
        self._results_log_file = None
        self._results_log_lock = threading.Lock()
        if settings.RESULTS_LOG_ENABLED:
            self._init_results_log()
        
        logger.info("QueueManager initialized")
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance of QueueManager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def start_worker(self):
        """Start the background worker thread."""
        with self._running_lock:
            if self.running:
                logger.warning("QueueManager worker thread already running")
                return
            
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="SER-QueueWorker"
            )
            self.worker_thread.start()
            logger.info("QueueManager worker thread started")
    
    def stop_worker(self):
        """Stop the background worker thread."""
        with self._running_lock:
            if not self.running:
                return
            
            self.running = False
        
        # Wait for thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info("Waiting for QueueManager worker thread to finish...")
            self.worker_thread.join(timeout=5.0)
            if self.worker_thread.is_alive():
                logger.warning("QueueManager worker thread did not finish within timeout")
            else:
                logger.info("QueueManager worker thread finished")
        
        self.worker_thread = None
    
    def enqueue_chunk(self, user_id: str, audio_file_path: str, timestamp: datetime, filename: Optional[str] = None) -> bool:
        """
        Enqueue an audio chunk for processing.
        
        Args:
            user_id: User identifier
            audio_file_path: Path to the audio file
            timestamp: Timestamp when the chunk was captured
            filename: Optional filename for display
        
        Returns:
            True if successfully enqueued, False otherwise
        """
        try:
            self.queue.put((user_id, audio_file_path, timestamp, filename), block=False)
            
            # Track queue item for dashboard
            with self._queue_lock:
                self._queue_items.append({
                    "user_id": user_id,
                    "timestamp": timestamp.isoformat(),
                    "filename": filename or os.path.basename(audio_file_path)
                })
            
            queue_size = self.queue.qsize()
            logger.info(
                f"✓ Enqueued chunk for user {user_id} "
                f"(filename: {filename or os.path.basename(audio_file_path)}, "
                f"queue size: {queue_size})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue chunk for user {user_id}: {e}")
            return False
    
    def _worker_loop(self):
        """Main worker loop that processes queued chunks."""
        logger.info("QueueManager worker loop started")
        
        while True:
            with self._running_lock:
                if not self.running:
                    break
            
            try:
                # Get next item from queue (with timeout to allow checking running flag)
                try:
                    user_id, audio_file_path, timestamp, filename = self.queue.get(timeout=1.0)
                    logger.info(
                        f"Worker: Processing queued item - user: {user_id}, "
                        f"file: {filename or os.path.basename(audio_file_path)}, "
                        f"queue size before: {self.queue.qsize() + 1}"
                    )
                except Empty:
                    continue
                
                # Remove from queue items tracking
                with self._queue_lock:
                    self._queue_items = [
                        item for item in self._queue_items
                        if not (item["user_id"] == user_id and item["timestamp"] == timestamp.isoformat())
                    ]
                
                # Set as processing
                with self._processing_lock:
                    self._processing_item = {
                        "user_id": user_id,
                        "started_at": datetime.now().isoformat(),
                        "result": None
                    }
                
                # Process the chunk
                logger.info(f"Worker: Starting processing for user {user_id}")
                result = self._process_chunk(user_id, audio_file_path, timestamp)
                
                if result:
                    logger.info(
                        f"Worker: Processing completed successfully - "
                        f"emotion: {result.get('emotion', 'N/A')}, "
                        f"confidence: {result.get('emotion_confidence', 0.0):.3f}"
                    )
                else:
                    logger.warning(f"Worker: Processing returned None (failed) for user {user_id}")
                
                # Update processing item with result
                with self._processing_lock:
                    if self._processing_item and self._processing_item["user_id"] == user_id:
                        self._processing_item["result"] = result
                
                # Add to recent results
                if result:
                    with self._results_lock:
                        self._recent_results.insert(0, {
                            "user_id": user_id,
                            "timestamp": timestamp.isoformat(),
                            **result
                        })
                        # Keep only last N results
                        if len(self._recent_results) > self._max_recent_results:
                            self._recent_results = self._recent_results[:self._max_recent_results]
                
                # Clear processing item after a short delay (to show result)
                time.sleep(0.5)
                with self._processing_lock:
                    if self._processing_item and self._processing_item["user_id"] == user_id:
                        self._processing_item = None
                
                # Mark task as done
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in QueueManager worker loop: {e}", exc_info=True)
        
        logger.info("QueueManager worker loop ended")
    
    def _process_chunk(self, user_id: str, audio_file_path: str, timestamp: datetime) -> Optional[Dict]:
        """
        Process a single audio chunk.
        
        Args:
            user_id: User identifier
            audio_file_path: Path to the audio file
            timestamp: Timestamp when the chunk was captured
        
        Returns:
            Dictionary with result data, or None on error
        """
        logger.debug(f"Processing chunk for user {user_id} (file: {audio_file_path})")
        
        try:
            # Run inference pipeline (stub for now)
            analysis_result = analyze_full(audio_file_path)
            
            # Create ChunkResult
            chunk_result = ChunkResult(
                timestamp=timestamp,
                emotion=analysis_result.get("emotion", "unknown"),
                emotion_confidence=analysis_result.get("emotion_confidence", 0.0),
                transcript=analysis_result.get("transcript"),
                language=analysis_result.get("language"),
                sentiment=analysis_result.get("sentiment"),
                sentiment_confidence=analysis_result.get("sentiment_confidence")
            )
            
            # Store in SessionManager
            session_id = self.session_manager.add_result(user_id, chunk_result)
            
            logger.info(
                f"Processed chunk for user {user_id}, session {session_id}: "
                f"emotion={chunk_result.emotion}, confidence={chunk_result.emotion_confidence:.3f}"
            )
            
            # Prepare result dict for dashboard and logging
            result_dict = {
                "emotion": chunk_result.emotion,
                "emotion_confidence": chunk_result.emotion_confidence,
                "transcript": chunk_result.transcript,
                "language": chunk_result.language,
                "sentiment": chunk_result.sentiment,
                "sentiment_confidence": chunk_result.sentiment_confidence
            }
            
            # Log result to file
            self._log_result_to_file(user_id, timestamp, result_dict)
            
            return result_dict
            
        except Exception as e:
            logger.error(
                f"Failed to process chunk for user {user_id} (file: {audio_file_path}): {e}",
                exc_info=True
            )
            return None
        finally:
            # Clean up temp file
            try:
                if os.path.exists(audio_file_path):
                    os.remove(audio_file_path)
                    logger.debug(f"Cleaned up temp file: {audio_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {audio_file_path}: {e}")
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
    
    def is_running(self) -> bool:
        """Check if worker thread is running."""
        with self._running_lock:
            return self.running
    
    def get_queue_items(self) -> List[Dict]:
        """Get list of items in queue (for dashboard)."""
        with self._queue_lock:
            return self._queue_items.copy()
    
    def get_processing_item(self) -> Optional[Dict]:
        """Get currently processing item (for dashboard)."""
        with self._processing_lock:
            return self._processing_item.copy() if self._processing_item else None
    
    def get_recent_results(self, limit: int = 50) -> List[Dict]:
        """Get recent processing results (for dashboard)."""
        with self._results_lock:
            return self._recent_results[:limit].copy()
    
    def _init_results_log(self):
        """Initialize results log file."""
        try:
            # Create log directory if it doesn't exist
            log_dir = settings.RESULTS_LOG_DIR
            os.makedirs(log_dir, exist_ok=True)
            
            # Create log file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"ser_results_{timestamp}.jsonl"
            log_path = os.path.join(log_dir, log_filename)
            
            self._results_log_file = log_path
            logger.info(f"Results log file initialized: {log_path}")
        except Exception as e:
            logger.error(f"Failed to initialize results log: {e}", exc_info=True)
            self._results_log_file = None
    
    def _log_result_to_file(self, user_id: str, timestamp: datetime, result: Dict):
        """
        Log processing result to JSONL file.
        
        Args:
            user_id: User identifier
            timestamp: Timestamp when chunk was captured
            result: Result dictionary with emotion, transcript, etc.
        """
        if not settings.RESULTS_LOG_ENABLED or not self._results_log_file:
            return
        
        try:
            log_entry = {
                "user_id": user_id,
                "timestamp": timestamp.isoformat(),
                "processed_at": datetime.now().isoformat(),
                **result
            }
            
            with self._results_log_lock:
                with open(self._results_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            logger.debug(f"Logged result to file: {self._results_log_file}")
        except Exception as e:
            logger.warning(f"Failed to log result to file: {e}", exc_info=True)
