"""
Sentiment Analysis ML Model

Sentiment analysis on transcribed text using transformer models.
Uses multilingual XLM-RoBERTa-based sentiment model.
"""


# Lazy imports
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Lazy-loaded pipeline (loaded on first use)
_sentiment_pipeline = None


def _load_sentiment_pipeline():
    """
    Lazy load sentiment analysis pipeline (only loads on first use).
    """
    global _sentiment_pipeline
    
    if _sentiment_pipeline is None:
        from transformers import pipeline
        
        logger.info("Loading sentiment analysis model (first use)...")
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-xlm-roberta-base-sentiment"
        )
        logger.info("Sentiment analysis model loaded successfully")
    
    return _sentiment_pipeline


def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    Analyze sentiment of transcribed text.
    
    Args:
        text: Transcribed text string
    
    Returns:
        Tuple of (sentiment_label, sentiment_score)
        sentiment_score is confidence (0.0-1.0)
    """
    logger.info("=" * 60)
    logger.info("SENTIMENT ANALYSIS: Starting")
    logger.info(f"  Input text length: {len(text)} chars")
    logger.info(f"  Input text preview: {text[:150]}...")
    
    # Handle empty or error text
    if not text or text.strip() == "" or text.startswith("Error:"):
        reason = "empty" if not text or text.strip() == "" else "error prefix"
        logger.warning(f"⚠ Skipping sentiment analysis - text is {reason}")
        logger.info("=" * 60)
        return "N/A", 0.0
    
    try:
        # Lazy load pipeline (only loads on first call)
        logger.info("  Loading sentiment pipeline...")
        sentiment_pipeline = _load_sentiment_pipeline()
        logger.info("  Pipeline loaded, running analysis...")
        
        # Run sentiment analysis
        result = sentiment_pipeline(text)
        
        # Extract label and score
        sentiment_label = result[0]['label']
        sentiment_score = result[0]['score']
        
        logger.info("=" * 60)
        logger.info("SENTIMENT ANALYSIS: Result")
        logger.info(f"  Label: {sentiment_label}")
        logger.info(f"  Confidence: {sentiment_score:.4f} ({sentiment_score*100:.2f}%)")
        logger.info("=" * 60)
        
        return sentiment_label, sentiment_score
        
    except Exception as e:
        logger.error(f"❌ Sentiment analysis failed: {e}", exc_info=True)
        logger.info("=" * 60)
        return "N/A", 0.0
