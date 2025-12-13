#!/usr/bin/env python3
"""
Test Script: Local Recording + Remote SER Service

This script records audio locally from the microphone and sends it to the remote SER service
for emotion recognition, transcription, and sentiment analysis.

Usage:
    python test_local_record_remote_ser.py [OPTIONS]
    
Options:
    --duration SECONDS    Recording duration per chunk in seconds (default: 5)
    --user-id UUID       User UUID (default: test user UUID)
    --file PATH          Use existing audio file instead of recording
    --url URL            SER service URL (default: http://localhost:8008 or SER_SERVICE_URL env var)
    --continuous         Continuously record and send chunks in a loop (press Ctrl+C to stop)
    --max-chunks N       Maximum number of chunks to send in continuous mode (default: infinite)
"""

import os
import sys
import argparse
import logging
import tempfile
import wave
import time
import requests
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# SER Service URL (can be overridden via --url argument or SER_SERVICE_URL env var)
SER_SERVICE_URL = os.getenv("SER_SERVICE_URL", "http://localhost:8008")
SER_ENDPOINT = "/analyze-speech"
SER_TIMEOUT = 30

# Default test user ID
DEFAULT_USER_ID = "96975f52-5b05-4eb1-bfa5-530485112518"


def capture_audio_from_mic(duration_seconds: float, sample_rate: int = 16000, chunk_size: int = 1600) -> Optional[list]:
    """
    Capture audio from microphone for specified duration.
    
    Args:
        duration_seconds: How long to record
        sample_rate: Sample rate in Hz (default: 16000)
        chunk_size: Frames per chunk (default: 1600)
    
    Returns:
        List of audio chunks (bytes) if successful, None if failed
    """
    try:
        import pyaudio
    except ImportError:
        logger.error("=" * 60)
        logger.error("ERROR: pyaudio is not installed!")
        logger.error("=" * 60)
        logger.error("To install pyaudio:")
        logger.error("  Windows: pip install pyaudio")
        logger.error("  Linux:   sudo apt-get install portaudio19-dev && pip install pyaudio")
        logger.error("  Mac:     brew install portaudio && pip install pyaudio")
        logger.error("=" * 60)
        return None
    
    pa = None
    stream = None
    
    try:
        logger.info(f"Initializing microphone (rate: {sample_rate}Hz, chunk: {chunk_size})...")
        pa = pyaudio.PyAudio()
        
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size
        )
        
        logger.info("Microphone active - speak now!")
        logger.info(f"Recording for {duration_seconds} seconds...")
        
        # Calculate number of chunks needed
        chunks_per_second = sample_rate // chunk_size
        total_chunks = int(duration_seconds * chunks_per_second)
        
        audio_chunks = []
        for i in range(total_chunks):
            try:
                chunk = stream.read(chunk_size, exception_on_overflow=False)
                audio_chunks.append(chunk)
                if (i + 1) % chunks_per_second == 0:
                    elapsed = (i + 1) // chunks_per_second
                    logger.info(f"Recording... {elapsed}/{int(duration_seconds)} seconds")
            except Exception as e:
                logger.error(f"Error capturing audio chunk: {e}")
                break
        
        logger.info(f"Captured {len(audio_chunks)} audio chunks")
        return audio_chunks
        
    except Exception as e:
        logger.error(f"Error during audio capture: {e}", exc_info=True)
        return None
    finally:
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:
                logger.debug(f"Error closing stream: {e}")
        if pa:
            try:
                pa.terminate()
            except Exception as e:
                logger.debug(f"Error terminating PyAudio: {e}")


def save_audio_to_wav(audio_chunks: list, sample_rate: int, output_path: Path) -> bool:
    """
    Save audio chunks to WAV file.
    
    Args:
        audio_chunks: List of audio chunks (bytes)
        sample_rate: Sample rate in Hz
        output_path: Path to save WAV file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with wave.open(str(output_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            # Write all chunks
            for chunk in audio_chunks:
                wav_file.writeframes(chunk)
        
        logger.info(f"Audio saved to: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving audio to WAV: {e}", exc_info=True)
        return False


def send_audio_to_ser(audio_file_path: Path, service_url: str, user_id: str) -> Optional[dict]:
    """
    Send audio file to SER service for analysis.
    
    Args:
        audio_file_path: Path to WAV audio file
        service_url: Base URL of SER service
        user_id: UUID of the user
    
    Returns:
        Dictionary with analysis results if successful, None if failed
    """
    try:
        url = f"{service_url}{SER_ENDPOINT}"
        logger.info(f"Sending audio to SER service: {url}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Audio file: {audio_file_path}")
        
        if not audio_file_path.exists():
            logger.error(f"Audio file not found: {audio_file_path}")
            return None
        
        with open(audio_file_path, 'rb') as audio_file:
            files = {'file': (audio_file_path.name, audio_file, 'audio/wav')}
            data = {'user_id': user_id}
            response = requests.post(url, files=files, data=data, timeout=SER_TIMEOUT)
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ SER service responded successfully")
            return result
        else:
            logger.error(f"❌ SER service error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"❌ Request timeout after {SER_TIMEOUT} seconds")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Connection error - is the SER service running at {service_url}?")
        logger.error(f"   Error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error sending audio to SER service: {e}", exc_info=True)
        return None


def display_result(result: dict):
    """
    Display analysis result in a readable format.
    
    Args:
        result: Analysis result dictionary from SER service
    """
    if not result:
        logger.warning("No result to display")
        return
    
    logger.info("=" * 60)
    logger.info("SER ANALYSIS RESULTS")
    logger.info("=" * 60)
    
    analysis_result = result.get("analysis_result", {})
    
    if analysis_result:
        emotion = analysis_result.get("emotion", "unknown")
        emotion_confidence = analysis_result.get("emotion_confidence", 0.0)
        transcript = analysis_result.get("transcript", "")
        language = analysis_result.get("language", "unknown")
        sentiment = analysis_result.get("sentiment", "unknown")
        sentiment_confidence = analysis_result.get("sentiment_confidence", 0.0)
        
        logger.info(f"Emotion: {emotion} (confidence: {emotion_confidence:.3f})")
        logger.info(f"Transcript: {transcript}")
        logger.info(f"Language: {language}")
        logger.info(f"Sentiment: {sentiment} (confidence: {sentiment_confidence:.3f})")
    else:
        logger.warning("No analysis_result in response")
        logger.info(f"Full response: {result}")
    
    logger.info("=" * 60)


def test_with_microphone(duration_seconds: float, user_id: str, continuous: bool = False, max_chunks: Optional[int] = None):
    """
    Test SER service with microphone recording.
    
    Args:
        duration_seconds: Recording duration per chunk
        user_id: User UUID
        continuous: If True, continuously record and send chunks in a loop
        max_chunks: Maximum number of chunks to send (None = infinite)
    """
    logger.info("=" * 60)
    logger.info("TEST: Local Recording + Remote SER Service")
    logger.info("=" * 60)
    logger.info(f"Recording duration per chunk: {duration_seconds} seconds")
    logger.info(f"User ID: {user_id}")
    logger.info(f"SER Service: {SER_SERVICE_URL}")
    if continuous:
        logger.info(f"Mode: CONTINUOUS (max_chunks: {max_chunks or 'infinite'})")
    else:
        logger.info("Mode: SINGLE RECORDING")
    logger.info("=" * 60)
    
    chunk_count = 0
    
    try:
        while True:
            chunk_count += 1
            logger.info("")
            logger.info(f"[Chunk #{chunk_count}] Starting recording...")
            
            # Step 1: Capture audio
            sample_rate = 16000
            chunk_size = 1600
            audio_chunks = capture_audio_from_mic(duration_seconds, sample_rate, chunk_size)
            
            if not audio_chunks:
                logger.error("Failed to capture audio")
                if not continuous:
                    return
                logger.warning("Continuing to next chunk...")
                time.sleep(1)
                continue
            
            # Step 2: Save to temporary WAV file
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', prefix=f'ser_test_chunk{chunk_count}_')
            temp_path = Path(temp_audio_file.name)
            temp_audio_file.close()
            
            if not save_audio_to_wav(audio_chunks, sample_rate, temp_path):
                logger.error("Failed to save audio file")
                if not continuous:
                    return
                logger.warning("Continuing to next chunk...")
                time.sleep(1)
                continue
            
            try:
                # Step 3: Send to SER service (non-blocking for continuous mode)
                logger.info(f"[Chunk #{chunk_count}] Sending to SER service...")
                result = send_audio_to_ser(temp_path, SER_SERVICE_URL, user_id)
                
                if result:
                    logger.info(f"[Chunk #{chunk_count}] ✅ Queued successfully")
                    if not continuous:
                        # Display result only for single recording mode
                        display_result(result)
                else:
                    logger.error(f"[Chunk #{chunk_count}] ❌ Failed to queue")
                    if not continuous:
                        return
                    
            finally:
                # Clean up temp file
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                        logger.debug(f"Cleaned up temp file: {temp_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file: {e}")
            
            # Break if not continuous mode
            if not continuous:
                break
            
            # Check max_chunks limit
            if max_chunks and chunk_count >= max_chunks:
                logger.info(f"Reached maximum chunks ({max_chunks}). Stopping.")
                break
            
            # Small delay before next chunk (optional, to avoid overwhelming the queue)
            logger.info(f"[Chunk #{chunk_count}] Waiting 1 second before next recording...")
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Recording interrupted by user (Ctrl+C)")
        logger.info(f"Total chunks sent: {chunk_count}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        if not continuous:
            raise


def test_with_file(audio_file_path: Path, user_id: str):
    """
    Test SER service with existing audio file.
    
    Args:
        audio_file_path: Path to audio file
        user_id: User UUID
    """
    logger.info("=" * 60)
    logger.info("TEST: Existing Audio File + Remote SER Service")
    logger.info("=" * 60)
    logger.info(f"Audio file: {audio_file_path}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"SER Service: {SER_SERVICE_URL}")
    logger.info("=" * 60)
    
    if not audio_file_path.exists():
        logger.error(f"Audio file not found: {audio_file_path}")
        return
    
    # Send to SER service
    result = send_audio_to_ser(audio_file_path, SER_SERVICE_URL, user_id)
    
    if result:
        display_result(result)
    else:
        logger.error("Failed to get result from SER service")


def main():
    """Main test function."""
    global SER_SERVICE_URL
    
    parser = argparse.ArgumentParser(
        description="Test local recording with remote SER service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record 5 seconds and send to SER service (single recording)
  python test_local_record_remote_ser.py
  
  # Record 10 seconds continuously (infinite loop, press Ctrl+C to stop)
  python test_local_record_remote_ser.py --duration 10 --continuous
  
  # Record 10 seconds, send 5 chunks then stop
  python test_local_record_remote_ser.py --duration 10 --continuous --max-chunks 5
  
  # Use existing audio file (single file only)
  python test_local_record_remote_ser.py --file path/to/audio.wav
  
  # Specify user ID and local service
  python test_local_record_remote_ser.py --url http://localhost:8008 --user-id "your-uuid-here" --continuous
        """
    )
    
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Recording duration in seconds (default: 5.0)"
    )
    
    parser.add_argument(
        "--user-id",
        type=str,
        default=DEFAULT_USER_ID,
        help=f"User UUID (default: {DEFAULT_USER_ID})"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="Use existing audio file instead of recording"
    )
    
    parser.add_argument(
        "--url",
        type=str,
        help=f"SER service URL (default: {SER_SERVICE_URL} or from SER_SERVICE_URL env var)"
    )
    
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continuously record and send chunks in a loop (default: False)"
    )
    
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Maximum number of chunks to send in continuous mode (default: infinite)"
    )
    
    args = parser.parse_args()
    
    # Override service URL if provided
    if args.url:
        SER_SERVICE_URL = args.url.rstrip('/')
    
    # Validate user ID format (basic UUID check)
    try:
        import uuid
        uuid.UUID(args.user_id)
    except ValueError:
        logger.error(f"Invalid user_id format: {args.user_id}. Must be a valid UUID.")
        sys.exit(1)
    
    # Run test
    if args.file:
        # Test with existing file (single file only, no continuous mode)
        audio_file = Path(args.file)
        test_with_file(audio_file, args.user_id)
    else:
        # Test with microphone recording
        test_with_microphone(
            args.duration, 
            args.user_id,
            continuous=args.continuous,
            max_chunks=args.max_chunks
        )


if __name__ == "__main__":
    main()
