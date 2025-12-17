"""
Audio Preprocessing Utilities

Audio preprocessing functions for emotion recognition.
CRITICAL CONSTRAINTS:
- No signal warping (no time-stretching or pitch-shifting)
- Edge-only silence removal (never remove internal pauses)
- Peak normalization only (no compression/AGC)
"""


# Imports moved to lazy loading
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
    
    CRITICAL: Preserves speech signal integrity - no warping, no internal silence removal.
    
    Args:
        input_path: Path to input audio file
        output_path: Path to save processed audio (if None, creates temp file)
        remove_silence: Whether to trim leading/trailing silence (edge-only, preserves internal pauses)
        normalize: Whether to apply peak normalization (NOT compression/AGC)
        noise_reduction: Whether to apply noise reduction (requires noisereduce library)
    
    Returns:
        Path to processed audio file
    """
    try:
        import librosa
        import soundfile as sf
        import numpy as np
        # Step 1: Load audio (auto-resample and mono conversion)
        y, sr = librosa.load(input_path, sr=TARGET_SAMPLE_RATE, mono=True)
        logger.info(f"Loaded audio: {len(y)} samples at {sr}Hz")
        
        # Step 2: Edge-only trim (preserves internal pauses)
        # librosa.effects.trim() ONLY removes leading/trailing silence, never internal pauses
        if remove_silence:
            original_len = len(y)
            y_trimmed, _ = librosa.effects.trim(y, top_db=30)
            # Safety check: Keep at least 30% of original audio length
            if len(y_trimmed) > original_len * 0.3:
                y = y_trimmed
                logger.info(
                    f"Trimmed edge silence: {len(y)} samples remaining "
                    f"({len(y)/original_len*100:.1f}% of original)"
                )
            else:
                logger.warning(
                    f"Trimmed audio too short ({len(y_trimmed)/original_len*100:.1f}% of original), "
                    f"keeping original"
                )
        
        # Step 3: Peak normalization (NOT compression/AGC)
        # Simple division by max - preserves dynamic range and natural speech dynamics
        if normalize:
            max_val = np.abs(y).max()
            if max_val > 0:
                y = y / max_val
                logger.info(
                    f"Applied peak normalization - max={np.abs(y).max():.6f}, "
                    f"mean={y.mean():.6f}, std={y.std():.6f}"
                )
            else:
                logger.warning("Audio is silent, skipping normalization")
        
        # Step 4: Optional noise reduction
        if noise_reduction:
            try:
                import noisereduce as nr
                y = nr.reduce_noise(y=y, sr=sr)
                logger.info("Applied noise reduction")
            except ImportError:
                logger.warning("noisereduce not installed, skipping noise reduction")
        
        # Step 5: Create output path if not provided
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.wav', prefix='processed_')
            os.close(fd)
        
        # Step 6: Save processed audio
        sf.write(output_path, y, TARGET_SAMPLE_RATE, format='WAV', subtype='PCM_16')
        logger.info(f"Saved processed audio to: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Audio preprocessing failed: {e}", exc_info=True)
        raise


def validate_audio(audio_path: str) -> Tuple[bool, str]:
    """
    Validate audio file before processing.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    import librosa
    
    try:
        # Check file exists
        if not os.path.exists(audio_path):
            return False, "Audio file does not exist"
        
        # Check file size
        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            return False, "Audio file is empty"
        
        # Try to load audio (quick validation with duration=1.0)
        y, sr = librosa.load(audio_path, sr=None, mono=False, duration=1.0)
        
        # Check duration
        if len(y) == 0:
            return False, "Audio file has no data"
        
        # Check sample rate (minimum 8kHz)
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
        Dictionary with audio metadata: sample_rate, duration_sec, channels, samples
    """
    import librosa
    
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
        logger.error(f"Failed to get audio info: {e}", exc_info=True)
        return {}
