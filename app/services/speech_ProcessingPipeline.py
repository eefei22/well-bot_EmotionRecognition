# app/services/speech_Pipeline.py

from app.services.speech_EmotionRecognition import predict_emotion
from app.services.speech_transcription import transcribe_audio
from app.services.speech_SentimentAnalysis import analyze_sentiment
from app.services.speech_AudioPreprocessing import preprocess_audio, validate_audio
from langdetect import detect
import os
import logging

logger = logging.getLogger(__name__)

def analyze_full(audio_path: str) -> dict:
    # Step 1: Validate audio file
    is_valid, error_msg = validate_audio(audio_path)
    if not is_valid:
        logger.error(f"Audio validation failed: {error_msg}")
        return {
            "emotion": "Error",
            "emotion_confidence": 0.0,
            "transcript": f"Audio validation failed: {error_msg}",
            "language": "N/A",
            "sentiment": "N/A",
            "sentiment_confidence": 0.0
        }
    
    # Step 2: Preprocess audio (creates temp processed file)
    processed_path = None
    try:
        processed_path = preprocess_audio(
            audio_path,
            remove_silence=True,
            normalize=True,
            noise_reduction=False  # Set to True if you install noisereduce
        )
        
        # Use processed audio for analysis
        audio_to_analyze = processed_path
        logger.info("Audio preprocessing completed successfully")
        
    except Exception as e:
        logger.warning(f"Audio preprocessing failed: {e}, using original file")
        # If preprocessing fails, use original
        audio_to_analyze = audio_path

    # Step 3: Run Speech Emotion Recognition (SER)
    try:
        emotion_label, emotion_confidence = predict_emotion(audio_to_analyze)
    except Exception as e:
        logger.error(f"Emotion recognition failed: {e}")
        emotion_label = f"Error: {str(e)}"
        emotion_confidence = 0.0

    # Step 4: Run Automatic Speech Recognition (ASR)
    try:
        transcript = transcribe_audio(audio_to_analyze)
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        transcript = f"Error: {str(e)}"

    # Step 5: Detect language from transcript
    try:
        if not transcript.startswith("Error:") and transcript.strip() != "":
            language_detected = detect(transcript)
        else:
            language_detected = "N/A"
    except Exception as e:
        logger.error(f"Language detection failed: {e}")
        language_detected = f"Error: {str(e)}"

    # Step 6: Run Sentiment Analysis
    try:
        if not transcript.startswith("Error:") and transcript.strip() != "":
            sentiment_label, sentiment_confidence = analyze_sentiment(transcript)
        else:
            sentiment_label = "N/A"
            sentiment_confidence = 0.0
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        sentiment_label = f"Error: {str(e)}"
        sentiment_confidence = 0.0
    
    # Step 7: Clean up temp processed file
    if processed_path and os.path.exists(processed_path):
        try:
            os.remove(processed_path)
            logger.debug(f"Cleaned up temp file: {processed_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file: {e}")

    # Return full result
    return {
        "emotion": emotion_label,
        "emotion_confidence": emotion_confidence,
        "transcript": transcript,
        "language": language_detected,
        "sentiment": sentiment_label,
        "sentiment_confidence": sentiment_confidence
    }
