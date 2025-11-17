# Well-Bot Speech Emotion Recognition (SER) Service - End-to-End Flow

## Service Overview

This is a cloud-deployed FastAPI service that processes audio files to extract emotion, transcription, language, and sentiment information, then stores the results in a Supabase database.

## Architecture

```
Edge App → Cloud Service (Well-Bot_SER) → Supabase Database
```

## End-to-End Flow

### 1. **Edge App Request**
   - **Endpoint**: `POST /analyze-speech`
   - **Content-Type**: `multipart/form-data`
   - **Body**: 
     - Field name: `file` - WAV audio file (required)
     - Field name: `user_id` - UUID of the user (required)
   - **Example**:
     ```python
     import requests
     
     url = "https://your-cloud-service-url/analyze-speech"
     user_id = "8517c97f-66ef-4955-86ed-531013d33d3e"  # User UUID from edge app
     
     with open("audio.wav", "rb") as audio_file:
         files = {"file": ("audio.wav", audio_file, "audio/wav")}
         data = {"user_id": user_id}
         response = requests.post(url, files=files, data=data)
     ```

### 2. **API Endpoint** (`app/api/speech.py`)
   - Receives the uploaded audio file and user_id from request
   - Validates user_id format (must be valid UUID)
   - Validates file extension (must be `.wav`)
   - Saves uploaded file to temporary location
   - Extracts audio metadata (sample_rate, duration)
   - Calls the processing pipeline
   - Maps results to database schema with user_id from request
   - Saves to Supabase database
   - Returns analysis result (optional - can be ignored)

### 3. **Audio Preprocessing Layer** (`app/services/speech_AudioPreprocessing.py`)
   - **Step 3.1: Validation**
     - Checks file exists and is not empty
     - Validates sample rate (minimum 8000Hz)
     - Verifies audio has data
   
   - **Step 3.2: Preprocessing**
     - Loads audio with librosa (auto-converts to mono, resamples to 16kHz)
     - Removes leading/trailing silence (trim)
     - Normalizes audio levels (peak normalization)
     - Optionally applies noise reduction (if enabled)
     - Saves processed audio to temporary file

### 4. **Processing Pipeline** (`app/services/speech_ProcessingPipeline.py`)
   - **Step 4.1: Speech Emotion Recognition (SER)**
     - Uses `superb/wav2vec2-base-superb-er` model
     - Processes preprocessed audio
     - Returns: emotion label + confidence score
   
   - **Step 4.2: Automatic Speech Recognition (ASR)**
     - Uses `openai/whisper-small` model
     - Transcribes audio to text
     - Returns: transcript text
   
   - **Step 4.3: Language Detection**
     - Uses `langdetect` library
     - Detects language from transcript
     - Returns: language code (e.g., "en", "zh-cn", "ms")
   
   - **Step 4.4: Sentiment Analysis**
     - Uses `cardiffnlp/twitter-xlm-roberta-base-sentiment` model
     - Analyzes transcript sentiment
     - Returns: sentiment label + confidence score

### 5. **Database Storage** (`app/crud/speech.py`)
   - Maps analysis results to database schema:
     - `emotion` → `predicted_emotion`
     - `emotion_confidence` → `emotion_confidence`
     - `transcript` → `transcript`
     - `language` → `language`
     - `sentiment` → `sentiment`
     - `sentiment_confidence` → `sentiment_confidence`
   - Adds required fields:
     - `user_id` (from request `user_id` parameter)
     - `timestamp` (current time)
     - `sample_rate` (from audio metadata)
     - `frame_size_ms` (default: 25.0)
     - `frame_stride_ms` (default: 10.0)
     - `duration_sec` (from audio metadata)
   - Inserts record into `voice_emotion` table in Supabase

### 6. **Response** (Optional - can be ignored)
   ```json
   {
     "analysis_result": {
       "emotion": "hap",
       "emotion_confidence": 0.98,
       "transcript": "Hello, how are you?",
       "language": "en",
       "sentiment": "positive",
       "sentiment_confidence": 0.85
     }
   }
   ```

## Configuration

### Environment Variables (`.env`)
```env
SUPABASE_URL=<your_supabase_url>
SUPABASE_SERVICE_ROLE_KEY=<your_service_role_key>
# Note: DEV_USER_ID is no longer used - user_id comes from request
```

### Database Table Schema
- Table: `voice_emotion`
- Required fields: `timestamp`, `sample_rate`, `frame_size_ms`, `frame_stride_ms`, `duration_sec`
- User identification: `user_id` (foreign key to `users` table)
- Analysis fields: `predicted_emotion`, `emotion_confidence`, `transcript`, `language`, `sentiment`, `sentiment_confidence`

## Error Handling

- **Audio Validation Failures**: Returns error in transcript field, continues processing
- **Preprocessing Failures**: Falls back to original audio file
- **Model Failures**: Returns error message in respective field, continues with other analyses
- **Database Failures**: Logs error but still returns analysis result

## Deployment Considerations

### Cloud Service Requirements
- Python 3.11+
- Port: 8008 (configurable)
- Dependencies: See `requirements.txt`
- Storage: Temporary file storage for audio processing
- Memory: Sufficient for ML models (recommended: 4GB+)

### Model Loading
- Models are downloaded from HuggingFace on first use
- Cached locally for subsequent requests
- Initial startup may take time to download models

### Performance
- Processing time: ~2-5 seconds per audio file (depending on length)
- Concurrent requests: Limited by model memory usage
- Recommended: Use async processing or queue for high volume

## Monitoring

- Logs: All processing steps are logged
- Database: Check `voice_emotion` table for successful saves
- Health: Can add `/health` endpoint for monitoring

## Security

- File validation: Only `.wav` files accepted
- User identification: Provided by edge app in each request (`user_id` parameter)
- UUID validation: User ID must be a valid UUID format
- Database: Uses Supabase service role key for authentication

