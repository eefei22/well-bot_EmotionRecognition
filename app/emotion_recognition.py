"""
Emotion Recognition ML Model

Speech emotion recognition using emotion2vec+ via FunASR.
Uses pre-trained model: iic/emotion2vec_plus_base (9-class emotions)
"""

import logging
import gc

# Imports moved to lazy loading in predict_emotion
from app.config import settings
from typing import Tuple, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded model (loaded on first use)
_ser_model = None

# emotion2vec+ 9-class emotion labels (from model)
EMOTION2VEC_LABELS = {
    0: "angry",
    1: "disgusted",
    2: "fearful",
    3: "happy",
    4: "neutral",
    5: "other",
    6: "sad",
    7: "surprised",
    8: "unknown"
}

# Mapping from 9-class to 7-class format (if EMOTION_FORMAT == "7class")
EMOTION_9_TO_7_MAPPING = {
    "angry": "ang",
    "disgusted": "dis",
    "fearful": "fea",
    "happy": "hap",
    "neutral": "neu",
    "other": "neu",  # Map "other" to neutral
    "sad": "sad",
    "surprised": "sur",
    "unknown": "unknown"
}

# Mapping from 9-class to 4-class format (capitalized for fusion service)
EMOTION_9_TO_4_MAPPING = {
    "angry": "Angry",
    "happy": "Happy",
    "sad": "Sad",
    "fearful": "Fear",
    "disgusted": "Angry",  # Negative emotion → Angry
    "surprised": "Fear",   # Unexpected/startled → Fear
    # neutral, other, unknown → None (skipped)
}


def _load_emotion_model():
    """
    Lazy load emotion recognition model (only loads on first use).
    Uses emotion2vec+ base model via FunASR.
    """
    global _ser_model
    
    if _ser_model is None:
        # Lazy import funasr here
        from funasr import AutoModel  # type: ignore
        
        logger.info("Loading emotion2vec+ model (first use)...")
        logger.info(f"  Model: {settings.EMOTION2VEC_MODEL}")
        logger.info(f"  Hub: {settings.FUNASR_HUB}")
        logger.info(f"  Format: {settings.EMOTION_FORMAT}")
        
        try:
            _ser_model = AutoModel(
                model=settings.EMOTION2VEC_MODEL,
                hub=settings.FUNASR_HUB
            )
            logger.info("✓ emotion2vec+ model loaded successfully")
            logger.info(f"  Available emotions (9-class): {list(EMOTION2VEC_LABELS.values())}")
        except Exception as e:
            logger.error(f"Failed to load emotion2vec+ model: {e}", exc_info=True)
            raise
    
    return _ser_model


def _map_emotion_label(emotion_9class: str) -> str:
    """
    Map 9-class emotion label to configured format (7-class or 9-class).
    
    Args:
        emotion_9class: Emotion label from emotion2vec+ (9-class format)
    
    Returns:
        Mapped emotion label based on EMOTION_FORMAT setting
    """
    if settings.EMOTION_FORMAT == "7class":
        return EMOTION_9_TO_7_MAPPING.get(emotion_9class.lower(), "unknown")
    else:
        # Return 9-class format (lowercase)
        return emotion_9class.lower()


def _map_to_4class(emotion_9class: str) -> Optional[str]:
    """
    Map 9-class emotion label to 4-class format (capitalized).
    
    Args:
        emotion_9class: Emotion label from emotion2vec+ (9-class format, lowercase)
    
    Returns:
        Mapped 4-class emotion label (capitalized: "Angry", "Sad", "Happy", "Fear") 
        or None if emotion should be skipped (neutral, other, unknown)
    """
    emotion_lower = emotion_9class.lower()
    return EMOTION_9_TO_4_MAPPING.get(emotion_lower)


def predict_emotion(audio_path: str) -> Tuple[Optional[str], float]:
    """
    Predict emotion from audio file using emotion2vec+ model.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Tuple of (emotion_label, confidence_score)
        Emotion label is 4-class format (capitalized: "Angry", "Sad", "Happy", "Fear")
        or None if emotion should be skipped (neutral, other, unknown)
        Confidence score is preserved from model output
    """
    try:
        import hashlib
        import librosa  # type: ignore
        import numpy as np  # type: ignore
        import soundfile as sf  # type: ignore
        import tempfile
        import os
        
        # Monkey-patch torchaudio if needed (for FunASR)
        import torchaudio  # type: ignore
        import torch  # type: ignore
        
        # We only need to patch it once, but checking attributes or re-patching is fine if simple
        if not getattr(torchaudio, "_is_patched_by_ser", False):
            _original_torchaudio_load = torchaudio.load
            
            def _patched_torchaudio_load(filepath, *args, **kwargs):
                """Patched version that uses soundfile directly, bypassing torchcodec entirely."""
                try:
                    # Use soundfile directly to load audio (bypasses torchcodec)
                    data, sample_rate = sf.read(filepath, dtype='float32')
                    # Convert to torch tensor matching torchaudio format: (channels, samples)
                    if len(data.shape) == 1:
                        # Mono: add channel dimension -> (1, samples)
                        data_tensor = torch.from_numpy(data).unsqueeze(0)
                    else:
                        # Multi-channel: transpose -> (channels, samples)
                        data_tensor = torch.from_numpy(data.T)
                    return data_tensor, sample_rate
                except Exception as e:
                    # Fallback to original if soundfile fails
                    import logging
                    logging.warning(f"Soundfile load failed for {filepath}, falling back: {e}")
                    kwargs['backend'] = 'soundfile'
                    return _original_torchaudio_load(filepath, *args, **kwargs)

            torchaudio.load = _patched_torchaudio_load
            setattr(torchaudio, "_is_patched_by_ser", True)
        
        
        # Lazy load model (only loads on first call)
        model = _load_emotion_model()
        
        # Log audio file info
        logger.info("=" * 60)
        logger.info("EMOTION RECOGNITION: Starting")
        logger.info(f"  File: {audio_path}")
        try:
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            logger.info(f"  File hash (first 8 chars): {file_hash}")
        except Exception:
            pass
        logger.info("=" * 60)
        
        # Pre-load audio with librosa to avoid torchaudio/torchcodec issues
        logger.info("  Loading audio with librosa...")
        audio_array, sample_rate = librosa.load(audio_path, sr=16000, mono=True)
        logger.info(f"  Loaded: shape={audio_array.shape}, sample_rate={sample_rate}Hz, duration={len(audio_array)/sample_rate:.2f}s")
        
        # Validate audio
        if len(audio_array) == 0:
            logger.error("Empty audio array")
            return None, 0.0
        
        if np.all(audio_array == 0):
            logger.warning("Audio is silent")
            return None, 0.0
        
        # Save to temporary WAV file for FunASR (FunASR expects file paths)
        temp_wav = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                temp_wav = tmp.name
                # Save as 16-bit PCM WAV (FunASR expects this format)
                sf.write(temp_wav, audio_array, 16000, format='WAV', subtype='PCM_16')
                logger.info(f"  Saved to temp file: {temp_wav}")
            
            # Run emotion recognition via FunASR with temp file path
            logger.info("  Running emotion2vec+ inference...")
            result = model.generate(
                input=temp_wav,  # Pass file path (FunASR will handle loading)
                output_dir=None,  # Don't save output files
                granularity="utterance",  # Utterance-level emotion
                extract_embedding=False  # Only return labels and scores
            )
        finally:
            # Clean up temp file
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                    logger.debug(f"  Cleaned up temp file: {temp_wav}")
                except Exception as e:
                    logger.warning(f"  Failed to clean up temp file: {e}")
        
        # Extract emotion label and score from FunASR result
        # FunASR returns: [{"labels": [label], "scores": [score]}] or similar format
        logger.info("=" * 60)
        logger.info("EMOTION RECOGNITION: Raw FunASR Result")
        logger.info(f"  Result type: {type(result)}")
        logger.info(f"  Result: {result}")
        logger.info("=" * 60)
        
        if not result or len(result) == 0:
            logger.warning("⚠ emotion2vec+ returned empty result")
            return None, 0.0
        
        # Handle FunASR result format
        # Result can be a list or dict, depending on FunASR version
        labels = None
        scores = None
        
        if isinstance(result, list):
            if len(result) > 0:
                first_result = result[0]
                logger.info(f"  First result type: {type(first_result)}")
                logger.info(f"  First result: {first_result}")
                if isinstance(first_result, dict):
                    labels = first_result.get("labels", [])
                    scores = first_result.get("scores", [])
                    # Also check for other possible keys
                    if not labels:
                        labels = first_result.get("label", [])
                    if not scores:
                        scores = first_result.get("score", [])
                else:
                    logger.warning(f"⚠ Unexpected result format: {type(first_result)}")
                    return None, 0.0
            else:
                logger.warning("⚠ Empty result list")
                return None, 0.0
        elif isinstance(result, dict):
            labels = result.get("labels", [])
            scores = result.get("scores", [])
            # Also check for other possible keys
            if not labels:
                labels = result.get("label", [])
            if not scores:
                scores = result.get("score", [])
        else:
            logger.warning(f"⚠ Unexpected result type: {type(result)}")
            return None, 0.0
        
        logger.info(f"  Extracted labels: {labels}")
        logger.info(f"  Extracted scores: {scores}")
        
        # Get predicted emotion (label with highest confidence score)
        if not labels or not scores:
            logger.warning("⚠ No labels or scores in result")
            return None, 0.0
        
        # Convert to lists if needed
        if not isinstance(labels, list):
            labels = [labels]
        if not isinstance(scores, list):
            scores = [scores]
        
        # Find index with highest confidence score
        scores_float = [float(s) for s in scores]
        max_idx = scores_float.index(max(scores_float))
        emotion_9class = labels[max_idx]
        confidence_score = scores_float[max_idx]
        
        logger.info(f"  Found max confidence at index {max_idx}: {emotion_9class} = {confidence_score:.6f}")
        
        # Extract English label from mixed Chinese/English format (e.g., "生气/angry" -> "angry")
        if "/" in str(emotion_9class):
            emotion_9class = str(emotion_9class).split("/")[-1].strip()
            logger.info(f"  Extracted English label from mixed format: {emotion_9class}")
        
        # Map to 4-class format
        emotion_label = _map_to_4class(emotion_9class)
        
        # Log all probabilities if available
        logger.info("=" * 60)
        logger.info("EMOTION RECOGNITION: Model Output")
        if isinstance(labels, list) and isinstance(scores, list) and len(labels) == len(scores):
            logger.info("  All probabilities:")
            for label, score in zip(labels, scores):
                mapped_4class = _map_to_4class(label)
                mapped_4class_str = mapped_4class if mapped_4class else "SKIPPED"
                logger.info(f"    {label} -> {mapped_4class_str}: {float(score):.4f} ({float(score)*100:.2f}%)")
        logger.info(f"  Predicted (9-class): {emotion_9class}")
        if emotion_label:
            logger.info(f"  Predicted (4-class): {emotion_label}")
        else:
            logger.info(f"  Predicted (4-class): SKIPPED (neutral/other/unknown)")
        logger.info(f"  Confidence: {confidence_score:.4f} ({confidence_score*100:.2f}%)")
        logger.info("=" * 60)
        
        # Clean up memory
        del result, audio_array
        gc.collect()
        
        # Return 4-class emotion or None if skipped
        return emotion_label, confidence_score
        
    except Exception as e:
        logger.error(f"❌ Emotion recognition failed: {e}", exc_info=True)
        return None, 0.0
