# app/services/speech_SentimentAnalysis.py

from transformers import pipeline
import logging

logger = logging.getLogger(__name__)

# Lazy-loaded pipeline (loaded on first use)
_sentiment_pipeline = None

def _load_sentiment_pipeline():
    """Lazy load sentiment analysis pipeline (only loads on first use)."""
    global _sentiment_pipeline
    
    if _sentiment_pipeline is None:
        logger.info("Loading sentiment analysis model (first use)...")
        _sentiment_pipeline = pipeline("sentiment-analysis", model="cardiffnlp/twitter-xlm-roberta-base-sentiment")
        logger.info("Sentiment analysis model loaded successfully")
    
    return _sentiment_pipeline

def analyze_sentiment(text: str) -> tuple[str, float]:
    # Lazy load pipeline (only loads on first call)
    sentiment_pipeline = _load_sentiment_pipeline()
    
    result = sentiment_pipeline(text)
    sentiment_label = result[0]['label']
    sentiment_score = result[0]['score']
    return sentiment_label, sentiment_score
