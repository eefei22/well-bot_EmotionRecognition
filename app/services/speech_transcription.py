# app/services/speech_Transcription.py

from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch
import torchaudio
import logging
import gc

logger = logging.getLogger(__name__)

# Whisper expects audio in 16kHz
TARGET_SAMPLING_RATE = 16000

# Lazy-loaded models (loaded on first use)
_processor = None
_model = None

def _load_transcription_model():
    """Lazy load transcription model (only loads on first use)."""
    global _processor, _model
    
    if _model is None:
        logger.info("Loading transcription model (first use)...")
        # Force CPU device to save memory (Cloud Run doesn't have GPUs)
        device = "cpu"
        _processor = WhisperProcessor.from_pretrained("openai/whisper-small")
        _model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-small")
        _model = _model.to(device)
        _model.eval()  # Set to evaluation mode
        logger.info("Transcription model loaded successfully on CPU")
    
    return _processor, _model

def transcribe_audio(audio_path: str) -> str:
    # Lazy load model (only loads on first call)
    processor, model = _load_transcription_model()
    
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
    
    # Clean up memory
    del predicted_ids, input_features, waveform
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    gc.collect()

    return transcription
