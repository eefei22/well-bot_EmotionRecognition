# app/services/speech_EmotionRecognition.py

from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
import torch
import torchaudio
import torch.nn.functional as F
import logging
import gc

logger = logging.getLogger(__name__)

# Lazy-loaded models (loaded on first use)
_feature_extractor = None
_model = None
_emotion_labels = None

def _load_emotion_model():
    """Lazy load emotion recognition model (only loads on first use)."""
    global _feature_extractor, _model, _emotion_labels
    
    if _model is None:
        logger.info("Loading emotion recognition model (first use)...")
        # Force CPU device to save memory (Cloud Run doesn't have GPUs)
        device = "cpu"
        _feature_extractor = AutoFeatureExtractor.from_pretrained("superb/wav2vec2-base-superb-er")
        _model = AutoModelForAudioClassification.from_pretrained("superb/wav2vec2-base-superb-er")
        _model = _model.to(device)
        _model.eval()  # Set to evaluation mode
        _emotion_labels = _model.config.id2label
        logger.info("Emotion recognition model loaded successfully on CPU")
    
    return _feature_extractor, _model, _emotion_labels

def predict_emotion(audio_path: str) -> tuple[str, float]:
    # Lazy load model (only loads on first call)
    feature_extractor, model, emotion_labels = _load_emotion_model()
    
    # Load audio
    waveform, sample_rate = torchaudio.load(audio_path)

    # Resample to 16kHz
    if sample_rate != 16000:
        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
        waveform = resampler(waveform)

    # Mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Prepare input
    inputs = feature_extractor(waveform.squeeze().numpy(), sampling_rate=16000, return_tensors="pt")

    # Inference
    with torch.no_grad():
        logits = model(**inputs).logits

    # Softmax to get probabilities
    probs = F.softmax(logits, dim=-1)
    predicted_class_id = int(logits.argmax(dim=-1))
    emotion_label = emotion_labels[predicted_class_id]
    confidence_score = float(probs[0, predicted_class_id])
    
    # Clean up memory
    del logits, probs, inputs, waveform
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    gc.collect()

    return emotion_label, confidence_score
