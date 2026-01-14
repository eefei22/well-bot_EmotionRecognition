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
from app.database import insert_voice_emotion, get_malaysia_timezone
from app.models import ChunkResult
from app.config import settings
from app.ser_result_logger import log_individual_result

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
        
        # Results logging is now in-memory (no file setup needed)
        
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
                        "started_at": datetime.now(get_malaysia_timezone()).isoformat(),
                        "filename": filename or os.path.basename(audio_file_path),
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
                        result_with_filename = {
                            "user_id": user_id,
                            "timestamp": timestamp.isoformat(),
                            "filename": filename or os.path.basename(audio_file_path),
                            **result
                        }
                        self._recent_results.insert(0, result_with_filename)
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
            # Get audio metadata for database insertion
            try:
                import librosa
                y, sr = librosa.load(audio_file_path, sr=None, mono=False)
                duration_sec = len(y) / sr if sr > 0 else 0.0
                # If stereo, convert to mono length
                if len(y.shape) > 1:
                    duration_sec = y.shape[1] / sr if sr > 0 else 0.0
                
                audio_metadata = {
                    "sample_rate": int(sr),
                    "frame_size_ms": 25.0,  # Default frame size
                    "frame_stride_ms": 10.0,  # Default frame stride
                    "duration_sec": duration_sec
                }
            except Exception as e:
                logger.warning(f"Failed to get audio metadata: {e}, using defaults")
                audio_metadata = {
                    "sample_rate": 16000,
                    "frame_size_ms": 25.0,
                    "frame_stride_ms": 10.0,
                    "duration_sec": 10.0
                }
            
            # Run inference pipeline
            analysis_result = analyze_full(audio_file_path)
            
            # Check if emotion was skipped (None)
            emotion = analysis_result.get("emotion")
            if emotion is None:
                logger.info(
                    f"Skipping chunk for user {user_id} - emotion is None "
                    f"(neutral/other/unknown, not stored in database)"
                )
                # Don't store skipped emotions in database
                # Don't add to recent results
                # Don't log individual result
                return None
            
            # Write directly to database (is_synthetic=False for real audio)
            db_result = insert_voice_emotion(
                user_id=user_id,
                timestamp=timestamp,
                analysis_result=analysis_result,
                audio_metadata=audio_metadata,
                is_synthetic=False
            )

            db_write_success = db_result is not None

            if db_write_success:
                logger.info(
                    f"Processed and stored chunk for user {user_id}: "
                    f"emotion={emotion}, "
                    f"confidence={analysis_result.get('emotion_confidence', 0.0):.3f}"
                )
            else:
                logger.warning(f"Failed to write chunk result to database for user {user_id}")

            # Prepare result dict for dashboard and logging
            result_dict = {
                "emotion": emotion,
                "emotion_confidence": analysis_result.get("emotion_confidence", 0.0),
                "transcript": analysis_result.get("transcript"),
                "language": analysis_result.get("language"),
                "sentiment": analysis_result.get("sentiment"),
                "sentiment_confidence": analysis_result.get("sentiment_confidence"),
                "db_write_success": db_write_success
            }
            
            # Log result to in-memory storage
            if settings.RESULTS_LOG_ENABLED:
                log_individual_result(user_id, timestamp.isoformat(), result_dict)
            
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
    
    # File logging methods removed - now using in-memory logging
