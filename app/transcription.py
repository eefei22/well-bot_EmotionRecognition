"""
Transcription Service

Automatic Speech Recognition (ASR) using Paraformer via FunASR.
Supports language-specific Paraformer models for improved accuracy.
"""

import logging
import gc

# Imports moved to lazy loading
from app.config import settings

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded models (cached by language)
_asr_models = {}

# Language code to Paraformer model mapping
LANGUAGE_TO_MODEL = {
    "en": settings.ASR_MODEL_EN,
    "zh": settings.ASR_MODEL_ZH,
    "ms": settings.ASR_MODEL_MS,
}


def _get_asr_model(language_code: Optional[str] = None):
    """
    Get or load Paraformer ASR model for specified language.
    
    Args:
        language_code: Language code ("en", "zh", "ms") or None for default
    
    Returns:
        FunASR AutoModel instance for ASR
    """
    # Determine model name based on language
    if language_code and language_code in LANGUAGE_TO_MODEL:
        model_name = LANGUAGE_TO_MODEL[language_code]
    else:
        # Default to English model
        model_name = settings.ASR_MODEL_EN
        if language_code:
            logger.debug(f"Language '{language_code}' not mapped, using default model: {model_name}")
    
    # Load model if not already cached
    if model_name not in _asr_models:
        # Lazy import funasr
        from funasr import AutoModel
        
        logger.info(f"Loading Paraformer ASR model: {model_name} (hub: {settings.FUNASR_HUB})")
        try:
            _asr_models[model_name] = AutoModel(
                model=model_name,
                hub=settings.FUNASR_HUB
            )
            logger.info(f"✓ Paraformer model '{model_name}' loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Paraformer model '{model_name}': {e}", exc_info=True)
            raise
    
    return _asr_models[model_name]


def transcribe_audio(
    audio_path: str,
    language_code: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Transcribe audio using Paraformer ASR model.
    
    Args:
        audio_path: Path to audio file
        language_code: Optional language code ("en", "zh", "ms")
                      If provided, uses language-specific Paraformer model
    
    Returns:
        Tuple of (transcription, detected_language_code)
        detected_language_code is the language code used, or None if auto-detected
    """
    try:
        import hashlib
        import librosa
        import numpy as np
        import soundfile as sf
        import tempfile
        import os
        
        # Monkey-patch torchaudio if needed (for FunASR)
        import torchaudio
        import torch
        
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
        
        
        logger.info("=" * 60)
        logger.info("TRANSCRIPTION: Starting")
        logger.info(f"  File: {audio_path}")
        logger.info(f"  Language parameter: {language_code or 'auto-detect'}")
        
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
            return "", None
        
        if np.all(audio_array == 0):
            logger.warning("Audio is silent")
            return "", None
        
        # Save to temporary WAV file for FunASR (FunASR expects file paths)
        temp_wav = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                temp_wav = tmp.name
                # Save as 16-bit PCM WAV (FunASR expects this format)
                sf.write(temp_wav, audio_array, 16000, format='WAV', subtype='PCM_16')
                logger.info(f"  Saved to temp file: {temp_wav}")
            
            # Get appropriate ASR model
            model = _get_asr_model(language_code)
            model_name = LANGUAGE_TO_MODEL.get(language_code, settings.ASR_MODEL_EN)
            
            # Run transcription via FunASR with temp file path
            logger.info(f"  Running Paraformer inference (model: {model_name})...")
            result = model.generate(
                input=temp_wav,  # Pass file path (FunASR will handle loading)
                sentence_timestamp=False  # We only need text, not timestamps
            )
        finally:
            # Clean up temp file
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                    logger.debug(f"  Cleaned up temp file: {temp_wav}")
                except Exception as e:
                    logger.warning(f"  Failed to clean up temp file: {e}")
        
        # Extract transcript from FunASR result
        # FunASR Paraformer returns: [{"text": "transcript", ...}] or {"text": "transcript"}
        transcription = ""
        detected_lang = language_code  # Use provided language or None
        
        if isinstance(result, list):
            if len(result) > 0:
                first_result = result[0]
                if isinstance(first_result, dict):
                    transcription = first_result.get("text", "")
                    # Try to get detected language if available
                    detected_lang = first_result.get("lang", detected_lang)
                elif isinstance(first_result, str):
                    transcription = first_result
                else:
                    logger.warning(f"⚠ Unexpected result format: {type(first_result)}")
            else:
                logger.warning("⚠ Empty result list")
        elif isinstance(result, dict):
            transcription = result.get("text", "")
            detected_lang = result.get("lang", detected_lang)
        elif isinstance(result, str):
            transcription = result
        else:
            logger.warning(f"⚠ Unexpected result type: {type(result)}")
        
        # Clean up memory
        del result, audio_array
        gc.collect()
        
        # Validate transcription
        if not transcription or len(transcription.strip()) == 0:
            logger.warning("⚠ Empty transcription returned from Paraformer")
            return "", detected_lang
        
        # Check for garbled output (excessive character repetition)
        if len(transcription) > 10:
            char_counts = {}
            for char in transcription:
                char_counts[char] = char_counts.get(char, 0) + 1
            max_repetition = max(char_counts.values()) if char_counts else 0
            repetition_ratio = max_repetition / len(transcription)
            
            logger.info(f"  Repetition analysis:")
            logger.info(f"    Max char repetition: {max_repetition}")
            logger.info(f"    Repetition ratio: {repetition_ratio:.4f} ({repetition_ratio*100:.2f}%)")
            logger.info(f"    Top 5 chars: {sorted(char_counts.items(), key=lambda x: x[1], reverse=True)[:5]}")
            
            if repetition_ratio > 0.5:  # More than 50% same character
                logger.warning(
                    f"❌ Transcription appears garbled (high repetition: {repetition_ratio:.2f})"
                )
                logger.warning(f"  Garbled text: {transcription[:100]}")
                return "", detected_lang
        
        logger.info("=" * 60)
        logger.info("TRANSCRIPTION: Success")
        logger.info(f"  Transcript: {transcription.strip()}")
        logger.info(f"  Detected language: {detected_lang or 'auto-detected'}")
        logger.info("=" * 60)
        
        return transcription.strip(), detected_lang
        
    except Exception as e:
        logger.error(f"❌ Transcription error: {e}", exc_info=True)
        return "", None
