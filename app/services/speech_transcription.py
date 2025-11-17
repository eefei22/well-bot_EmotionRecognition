# app/services/speech_Transcription.py

from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch
import torchaudio

# Load processor + model
processor = WhisperProcessor.from_pretrained("openai/whisper-small")
model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-small")

# Whisper expects audio in 16kHz
TARGET_SAMPLING_RATE = 16000

def transcribe_audio(audio_path: str) -> str:
    # Load audio
    waveform, sample_rate = torchaudio.load(audio_path)

    # Resample if needed
    if sample_rate != TARGET_SAMPLING_RATE:
        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=TARGET_SAMPLING_RATE)
        waveform = resampler(waveform)

    # Mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Prepare input for Whisper
    input_features = processor(
        waveform.squeeze().numpy(), 
        sampling_rate=TARGET_SAMPLING_RATE, 
        return_tensors="pt"
    ).input_features

    # Generate transcription
    predicted_ids = model.generate(input_features)
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

    return transcription
