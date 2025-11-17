# app/services/speech_AudioPreprocessing.py

import librosa
import soundfile as sf
import numpy as np
import tempfile
import os
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Target audio parameters
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1  # Mono


def preprocess_audio(
    input_path: str, 
    output_path: Optional[str] = None,
    remove_silence: bool = True,
    normalize: bool = True,
    noise_reduction: bool = False
) -> str:
    """
    Preprocess raw audio file for emotion recognition.
    
    Args:
        input_path: Path to input audio file
        output_path: Path to save processed audio (if None, creates temp file)
        remove_silence: Whether to trim leading/trailing silence
        normalize: Whether to normalize audio levels
        noise_reduction: Whether to apply noise reduction (requires noisereduce library)
    
    Returns:
        Path to processed audio file
    """
    try:
        # Load audio with librosa (automatically converts to mono and resamples)
        y, sr = librosa.load(input_path, sr=TARGET_SAMPLE_RATE, mono=True)
        
        logger.info(f"Loaded audio: {len(y)} samples at {sr}Hz")
        
        # Remove silence (trim leading/trailing silence)
        if remove_silence:
            y_trimmed, _ = librosa.effects.trim(y, top_db=20)
            if len(y_trimmed) > 0:
                y = y_trimmed
                logger.info(f"Trimmed silence: {len(y)} samples remaining")
        
        # Normalize audio
        if normalize:
            # Peak normalization to [-1, 1]
            max_val = np.abs(y).max()
            if max_val > 0:
                y = y / max_val
            logger.info("Applied peak normalization")
        
        # Noise reduction (optional - requires noisereduce library)
        if noise_reduction:
            try:
                import noisereduce as nr
                y = nr.reduce_noise(y=y, sr=sr)
                logger.info("Applied noise reduction")
            except ImportError:
                logger.warning("noisereduce not installed, skipping noise reduction")
        
        # Create output path if not provided
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.wav', prefix='processed_')
            os.close(fd)
        
        # Save processed audio
        sf.write(output_path, y, TARGET_SAMPLE_RATE, format='WAV', subtype='PCM_16')
        logger.info(f"Saved processed audio to: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Audio preprocessing failed: {e}")
        raise


def validate_audio(audio_path: str) -> Tuple[bool, str]:
    """
    Validate audio file before processing.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check file exists
        if not os.path.exists(audio_path):
            return False, "Audio file does not exist"
        
        # Check file size
        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            return False, "Audio file is empty"
        
        # Try to load audio
        y, sr = librosa.load(audio_path, sr=None, mono=False, duration=1.0)
        
        # Check duration
        if len(y) == 0:
            return False, "Audio file has no data"
        
        # Check sample rate (warn if too low/high)
        if sr < 8000:
            return False, f"Sample rate too low: {sr}Hz (minimum 8000Hz)"
        
        if sr > 48000:
            logger.warning(f"High sample rate: {sr}Hz (will be resampled to 16kHz)")
        
        return True, "Audio file is valid"
        
    except Exception as e:
        return False, f"Audio validation failed: {str(e)}"


def get_audio_info(audio_path: str) -> dict:
    """
    Get audio file information.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Dictionary with audio metadata
    """
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        duration = len(y) / sr if sr > 0 else 0
        
        return {
            "sample_rate": int(sr),
            "duration_sec": float(duration),
            "channels": 1 if len(y.shape) == 1 else y.shape[0],
            "samples": len(y) if len(y.shape) == 1 else y.shape[1]
        }
    except Exception as e:
        logger.error(f"Failed to get audio info: {e}")
        return {}

