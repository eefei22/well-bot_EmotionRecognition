# app/services/speech_Pipeline.py

from app.services.speech_EmotionRecognition import predict_emotion
from app.services.speech_transcription import transcribe_audio
from app.services.speech_SentimentAnalysis import analyze_sentiment
from langdetect import detect

def analyze_full(audio_path: str) -> dict:
    # Run SER
    try:
        emotion_label, emotion_confidence = predict_emotion(audio_path)
    except Exception as e:
        emotion_label = f"Error: {str(e)}"
        emotion_confidence = 0.0

    # Run ASR
    try:
        transcript = transcribe_audio(audio_path)
    except Exception as e:
        transcript = f"Error: {str(e)}"

    # Detect language
    try:
        if not transcript.startswith("Error:") and transcript.strip() != "":
            language_detected = detect(transcript)
        else:
            language_detected = "N/A"
    except Exception as e:
        language_detected = f"Error: {str(e)}"

    # Run Sentiment
    try:
        if not transcript.startswith("Error:") and transcript.strip() != "":
            sentiment_label, sentiment_confidence = analyze_sentiment(transcript)
        else:
            sentiment_label = "N/A"
            sentiment_confidence = 0.0
    except Exception as e:
        sentiment_label = f"Error: {str(e)}"
        sentiment_confidence = 0.0

    # Return full result
    return {
        "emotion": emotion_label,
        "emotion_confidence": emotion_confidence,
        "transcript": transcript,
        "language": language_detected,
        "sentiment": sentiment_label,
        "sentiment_confidence": sentiment_confidence
    }
