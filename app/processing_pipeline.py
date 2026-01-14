"""
Processing Pipeline

Orchestrates all ML services (emotion recognition, transcription, sentiment analysis).
CRITICAL: Language detection happens BEFORE full transcription (not as fallback).
"""

import os
import logging
from langdetect import detect

from app.audio_preprocessing import preprocess_audio, validate_audio
from app.emotion_recognition import predict_emotion
from app.transcription import transcribe_audio
from app.sentiment_analysis import analyze_sentiment

logger = logging.getLogger(__name__)


def _map_language(langdetect_code: str) -> str:
    """
    Map langdetect language code to supported languages.
    
    Args:
        langdetect_code: Language code from langdetect library
    
    Returns:
        Supported language code (en, ms, zh) or None if not supported
    """
    mapping = {
        "en": "en",
        "ms": "ms",
        "id": "ms",      # Indonesian → Malay
        "zh": "zh",
        "zh-cn": "zh",   # Simplified Chinese → Chinese
        "zh-tw": "zh"    # Traditional Chinese → Chinese
    }
    
    # Try exact match
    if langdetect_code in mapping:
        return mapping[langdetect_code]
    
    # Try prefix match (e.g., "zh-cn" matches "zh")
    for code, mapped in mapping.items():
        if langdetect_code.startswith(code.split("-")[0]):
            return mapped
    
    # Not supported, will use auto-detect fallback
    return None


def analyze_full(audio_path: str) -> dict:
    """
    Full audio analysis pipeline.
    
    Orchestrates all ML components in correct sequence:
    1. Validate audio
    2. Preprocess audio (for emotion recognition)
    3. Run emotion recognition (on preprocessed audio)
    4. Run quick transcription for language detection
    5. Detect language from quick transcript
    6. Run full transcription with language parameter
    7. Run sentiment analysis (on transcript)
    8. Clean up temporary files
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Dictionary with analysis results:
        - emotion: Emotion label (lowercase: "hap", "sad", "ang", etc.)
        - emotion_confidence: Confidence score (0.0-1.0)
        - transcript: Transcribed text
        - language: Detected language code (en/ms/zh/unknown)
        - sentiment: Sentiment label
        - sentiment_confidence: Confidence score (0.0-1.0)
    """
    import hashlib
    
    # Log pipeline start with file identification
    file_hash = ""
    try:
        with open(audio_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
    except Exception:
        pass
    
    logger.info("=" * 80)
    logger.info(f"PIPELINE START: Processing audio file")
    logger.info(f"  File: {audio_path}")
    logger.info(f"  File hash (first 8 chars): {file_hash}")
    logger.info("=" * 80)
    
    # Step 1: Validate audio
    logger.info("[Step 1/9] Validating audio file...")
    is_valid, error_msg = validate_audio(audio_path)
    if not is_valid:
        logger.error(f"❌ Audio validation failed: {error_msg}")
        return {
            "emotion": "Error",
            "emotion_confidence": 0.0,
            "transcript": f"Audio validation failed: {error_msg}",
            "language": "N/A",
            "sentiment": "N/A",
            "sentiment_confidence": 0.0
        }
    logger.info("✓ Audio validation passed")
    
    # Step 2: Preprocess audio for emotion recognition
    logger.info("[Step 2/9] Preprocessing audio for emotion recognition...")
    processed_path = None
    try:
        processed_path = preprocess_audio(
            audio_path,
            remove_silence=True,
            normalize=True,
            noise_reduction=False  # Optional: set to True if noisereduce is installed
        )
        logger.info(f"✓ Audio preprocessing completed: {processed_path}")
    except Exception as e:
        logger.warning(f"⚠ Audio preprocessing failed: {e}, using original file for emotion recognition", exc_info=True)
        processed_path = None
    
    # Step 3: Emotion recognition (on preprocessed audio)
    logger.info("[Step 3/9] Running emotion recognition...")
    emotion_label = None
    emotion_conf = 0.0
    try:
        emotion_audio = processed_path if processed_path else audio_path
        logger.info(f"  Using audio file: {emotion_audio}")
        logger.info(f"  File type: {'Preprocessed' if processed_path else 'Original'}")
        emotion_label, emotion_conf = predict_emotion(emotion_audio)
        if emotion_label:
            logger.info(f"✓ Emotion detected: {emotion_label} (confidence: {emotion_conf:.4f})")
        else:
            logger.info(f"⚠ Emotion skipped (neutral/other/unknown) - confidence: {emotion_conf:.4f}")
    except Exception as e:
        logger.error(f"❌ Emotion recognition failed: {e}", exc_info=True)
        emotion_label = None
        emotion_conf = 0.0
    
    # Step 4: Quick transcription for language detection
    logger.info("[Step 4/9] Running quick transcription for language detection...")
    transcript_quick = ""
    language_code = None
    try:
        transcript_quick, _ = transcribe_audio(audio_path)  # Auto-detect, faster
        if transcript_quick:
            logger.info(f"✓ Quick transcript received: {len(transcript_quick)} chars")
            logger.info(f"  Preview: {transcript_quick[:150]}...")
        else:
            logger.warning("⚠ Quick transcription returned empty result")
    except Exception as e:
        logger.error(f"❌ Quick transcription failed: {e}", exc_info=True)
    
    # Step 5: Detect language from quick transcript
    logger.info("[Step 5/9] Detecting language from transcript...")
    if transcript_quick and transcript_quick.strip():
        try:
            lang_code = detect(transcript_quick)
            logger.info(f"  langdetect result: {lang_code}")
            language_code = _map_language(lang_code)
            if language_code:
                logger.info(f"✓ Detected language: {language_code} (from langdetect: {lang_code})")
            else:
                logger.warning(f"⚠ Language '{lang_code}' not mapped, will use auto-detect")
        except Exception as e:
            logger.error(f"❌ Language detection failed: {e}", exc_info=True)
    else:
        logger.warning("⚠ Skipping language detection (no transcript available)")
    
    # Step 6: Full transcription with language parameter
    logger.info("[Step 6/9] Running full transcription with language parameter...")
    transcript = ""
    detected_lang = None
    try:
        logger.info(f"  Language parameter: {language_code or 'auto-detect'}")
        transcript, detected_lang = transcribe_audio(
            audio_path,
            language_code=language_code  # Pass detected language for better accuracy
        )
        if transcript:
            logger.info(f"✓ Transcription successful: {len(transcript)} chars")
            logger.info(f"  Full transcript: {transcript}")
        else:
            logger.warning("⚠ Transcription returned empty result")
    except Exception as e:
        logger.error(f"❌ Transcription failed: {e}", exc_info=True)
    
    # Step 7: Final language (use detected from transcription or langdetect)
    logger.info("[Step 7/9] Determining final language...")
    final_language = detected_lang or language_code or "unknown"
    logger.info(f"  Final language: {final_language}")
    
    # Step 8: Sentiment analysis
    logger.info("[Step 8/9] Running sentiment analysis...")
    sentiment_label = "N/A"
    sentiment_conf = 0.0
    try:
        if transcript and not transcript.startswith("Error:") and transcript.strip() != "":
            logger.info(f"  Analyzing sentiment for transcript: {transcript[:100]}...")
            sentiment_label, sentiment_conf = analyze_sentiment(transcript)
            logger.info(f"✓ Sentiment: {sentiment_label} (confidence: {sentiment_conf:.4f})")
        else:
            logger.warning(f"⚠ Skipping sentiment analysis - transcript status: "
                         f"empty={not transcript}, "
                         f"starts_with_error={transcript.startswith('Error:') if transcript else False}, "
                         f"is_whitespace={transcript.strip() == '' if transcript else True}")
    except Exception as e:
        logger.error(f"❌ Sentiment analysis failed: {e}", exc_info=True)
    
    # Step 9: Cleanup temporary files
    logger.info("[Step 9/9] Cleaning up temporary files...")
    if processed_path and os.path.exists(processed_path):
        try:
            os.remove(processed_path)
            logger.info(f"✓ Cleaned up temp processed file: {processed_path}")
        except Exception as e:
            logger.warning(f"⚠ Failed to clean up temp processed file: {e}")
    
    # Return full result
    result = {
        "emotion": emotion_label,  # Can be None if skipped
        "emotion_confidence": emotion_conf,
        "transcript": transcript,
        "language": final_language,
        "sentiment": sentiment_label,
        "sentiment_confidence": sentiment_conf
    }
    
    logger.info("=" * 80)
    logger.info("PIPELINE COMPLETE: Final results")
    emotion_display = emotion_label if emotion_label else "SKIPPED (None)"
    logger.info(f"  Emotion: {emotion_display} ({emotion_conf:.4f})")
    logger.info(f"  Transcript: {transcript[:100] if transcript else 'EMPTY'}...")
    logger.info(f"  Language: {final_language}")
    logger.info(f"  Sentiment: {sentiment_label} ({sentiment_conf:.4f})")
    logger.info(f"  File hash: {file_hash}")
    logger.info("=" * 80)
    
    return result
