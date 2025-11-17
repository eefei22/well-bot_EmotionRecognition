# app/services/speech_SentimentAnalysis.py

from transformers import pipeline

# Load sentiment pipeline
sentiment_pipeline = pipeline("sentiment-analysis", model="cardiffnlp/twitter-xlm-roberta-base-sentiment")

def analyze_sentiment(text: str) -> tuple[str, float]:
    result = sentiment_pipeline(text)
    sentiment_label = result[0]['label']
    sentiment_score = result[0]['score']
    return sentiment_label, sentiment_score
