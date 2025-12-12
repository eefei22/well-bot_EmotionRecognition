# FunASR + emotion2vec+ Migration Notes

## Migration Completed

The SER service has been migrated from wav2vec2 + Whisper to FunASR + emotion2vec+ stack.

## Changes Made

### 1. Dependencies (`requirements.txt`)
- Added: `funasr>=1.0.0`, `modelscope>=1.0.0`
- Kept: `transformers` (still needed for sentiment analysis)
- Kept: `librosa`, `soundfile` (still needed for audio validation/preprocessing)

### 2. Configuration (`ser/config.py`)
- Added FunASR hub setting: `FUNASR_HUB = "hf"` (HuggingFace)
- Added emotion model: `EMOTION2VEC_MODEL = "iic/emotion2vec_plus_base"`
- Added emotion format: `EMOTION_FORMAT = "7class"` (configurable: "7class" or "9class")
- Added Paraformer ASR model settings (language-specific)

### 3. Emotion Recognition (`ser/emotion_recognition.py`)
- **Replaced**: wav2vec2 → emotion2vec+ base via FunASR
- **Model**: `iic/emotion2vec_plus_base` (~90M parameters)
- **Emotions**: 9-class (angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown)
- **Mapping**: Configurable 9-class → 7-class mapping (if `EMOTION_FORMAT == "7class"`)
- **Function signature**: Unchanged (`predict_emotion(audio_path: str) -> Tuple[str, float]`)

### 4. Transcription (`ser/transcription.py`)
- **Replaced**: Whisper → Paraformer via FunASR
- **Models**: Language-specific Paraformer models (en/zh/ms)
- **Language detection**: Uses language-specific models for better accuracy
- **Function signature**: Unchanged (`transcribe_audio(audio_path: str, language_code: Optional[str] = None) -> Tuple[str, Optional[str]]`)

### 5. Processing Pipeline (`ser/processing_pipeline.py`)
- **No changes needed** - pipeline works with new models due to maintained function signatures
- Language detection flow remains: quick transcription → langdetect → full transcription with language parameter

### 6. Models (`ser/models.py`)
- **No changes needed** - existing models support both 7-class and 9-class emotion formats

## Model Information

### emotion2vec+ Base Model
- **Model ID**: `iic/emotion2vec_plus_base`
- **Size**: ~90M parameters
- **Emotions**: 9-class
  - 0: angry
  - 1: disgusted
  - 2: fearful
  - 3: happy
  - 4: neutral
  - 5: other
  - 6: sad
  - 7: surprised
  - 8: unknown

### Paraformer ASR Models
- **Default**: `paraformer-zh` (Chinese, supports multiple languages)
- **Note**: Actual model names need verification from FunASR model zoo
- Models are cached per language to avoid reloading

## Configuration Options

### Environment Variables (`.env`)
```bash
# FunASR Configuration
FUNASR_HUB=hf                    # "hf" for HuggingFace, "ms" for ModelScope
EMOTION2VEC_MODEL=iic/emotion2vec_plus_base
EMOTION_FORMAT=7class            # "7class" or "9class"

# Paraformer ASR Models (verify actual names)
ASR_MODEL_EN=paraformer-zh      # English model
ASR_MODEL_ZH=paraformer-zh      # Chinese model
ASR_MODEL_MS=paraformer-zh      # Malay model
```

## Emotion Label Mapping

### 9-class → 7-class Mapping (when `EMOTION_FORMAT == "7class"`)
- `angry` → `ang`
- `disgusted` → `dis`
- `fearful` → `fea`
- `happy` → `hap`
- `neutral` → `neu`
- `other` → `neu` (mapped to neutral)
- `sad` → `sad`
- `surprised` → `sur`
- `unknown` → `unknown`

## Testing Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Test emotion recognition with sample audio
- [ ] Test transcription with English audio
- [ ] Test transcription with Chinese audio
- [ ] Test transcription with Malay audio
- [ ] Test full pipeline end-to-end
- [ ] Verify dashboard displays results correctly
- [ ] Verify emotion format (7-class vs 9-class) based on config
- [ ] Monitor model download and caching behavior

## Known Issues / TODOs

1. **Paraformer Model Names**: Actual Paraformer model names need verification from FunASR model zoo
   - Current config uses `paraformer-zh` as default for all languages
   - May need to update to language-specific models once verified

2. **Model Download**: FunASR will download models on first use (~300MB+ per model)
   - Models are cached locally after first download
   - Ensure sufficient disk space

3. **Performance**: emotion2vec+ base is similar size to wav2vec2, expect similar inference time
   - Paraformer may be faster than Whisper for some languages

## Rollback

If issues arise, the old implementation can be restored by:
1. Reverting `ser/emotion_recognition.py` to wav2vec2 version
2. Reverting `ser/transcription.py` to Whisper version
3. Removing FunASR dependencies from `requirements.txt`

## References

- emotion2vec GitHub: https://github.com/ddlBoJack/emotion2vec
- FunASR GitHub: https://github.com/modelscope/FunASR
- emotion2vec+ Model: https://huggingface.co/emotion2vec/emotion2vec_plus_base

