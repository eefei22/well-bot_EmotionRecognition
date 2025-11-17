# app/services/speech_EmotionRecognition.py

from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
import torch
import torchaudio
import torch.nn.functional as F

# Load feature extractor + model
feature_extractor = AutoFeatureExtractor.from_pretrained("superb/wav2vec2-base-superb-er")
model = AutoModelForAudioClassification.from_pretrained("superb/wav2vec2-base-superb-er")

# Define emotion labels
EMOTION_LABELS = model.config.id2label

def predict_emotion(audio_path: str) -> tuple[str, float]:
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
    emotion_label = EMOTION_LABELS[predicted_class_id]
    confidence_score = float(probs[0, predicted_class_id])

    return emotion_label, confidence_score
