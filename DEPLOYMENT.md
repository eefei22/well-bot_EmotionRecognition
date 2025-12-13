# Well-Bot_SER Cloud Deployment Guide

## Overview

This guide covers deploying the Well-Bot Speech Emotion Recognition (SER) service to Google Cloud Run.

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **Google Cloud SDK (gcloud)** installed and configured
3. **Docker** installed (for local testing)
4. **Supabase Project** with database configured

## Step 1: Prepare Environment Variables

Create a `.env` file with the following variables (these will be set in Cloud Run):

```env
SUPABASE_URL=<your_supabase_url>
SUPABASE_SERVICE_ROLE_KEY=<your_service_role_key>
```

**Note**: 
- For Cloud Run, these will be set as environment variables in the service configuration.
- `user_id` is no longer required in `.env` - it is passed by the edge app in each request.

## Step 2: Build and Test Docker Image Locally (Optional)

```bash
# Build the Docker image
docker build -t well-bot-ser:latest .

# Test locally
docker run -p 8008:8008 --env-file .env well-bot-ser:latest
```

## Step 3: Deploy to Google Cloud Run

### Option A: Deploy from Source (Recommended)

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Deploy to Cloud Run
gcloud run deploy well-bot-ser \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars SUPABASE_URL=<your_supabase_url> \
  --set-env-vars SUPABASE_SERVICE_ROLE_KEY=<your_service_role_key>
```

### Option B: Deploy from Container Registry

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/well-bot-ser:latest

# Deploy from container image
gcloud run deploy well-bot-ser \
  --image gcr.io/YOUR_PROJECT_ID/well-bot-ser:latest \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars SUPABASE_URL=<your_supabase_url> \
  --set-env-vars SUPABASE_SERVICE_ROLE_KEY=<your_service_role_key>
```

## Step 4: Get Your Service URL

After deployment, Cloud Run will provide a URL:

```bash
# Get the service URL
gcloud run services describe well-bot-ser --region asia-south1 --format 'value(status.url)'
```

The URL will look like:
```
https://well-bot-ser-XXXXX-XX.a.run.app
```

## Step 5: Update Edge App Configuration

Update your edge app's `.env` or configuration file:

```env
SER_SERVICE_URL=https://well-bot-ser-XXXXX-XX.a.run.app
```

Or update the test script:
```bash
export SER_SERVICE_URL=https://well-bot-ser-XXXXX-XX.a.run.app
python test_micstream_ser.py --file audio.wav
```

## Configuration Details

### Resource Requirements

- **Memory**: 2Gi (recommended for ML models)
- **CPU**: 2 (for faster processing)
- **Timeout**: 300 seconds (5 minutes for long audio files)
- **Max Instances**: 10 (adjust based on expected load)

### Environment Variables

Set these in Cloud Run:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key

**Note**: `user_id` is passed by the edge app in each request, not via environment variables.

### Port Configuration

- Cloud Run sets `PORT=8080` environment variable automatically
- The Dockerfile uses this PORT variable (defaults to 8008 for local development)
- Cloud Run automatically maps this to HTTPS on port 443
- **Note**: Do not use `--port` flag in deployment - Cloud Run handles port mapping automatically

## Testing the Deployment

### Test with curl:

```bash
curl -X POST "https://your-service-url.run.app/analyze-speech" \
  -F "file=@audio.wav" \
  -F "user_id=96975f52-5b05-4eb1-bfa5-530485112518"
```

### Test with Python:

```python
import requests

url = "https://your-service-url.run.app/analyze-speech"
user_id = "96975f52-5b05-4eb1-bfa5-530485112518"  # User UUID

with open("audio.wav", "rb") as f:
    files = {"file": ("audio.wav", f, "audio/wav")}
    data = {"user_id": user_id}
    response = requests.post(url, files=files, data=data)
    print(response.json())
```

### Test with the test script:

```bash
cd Well-Bot_edge/backend/testing
export SER_SERVICE_URL=https://your-service-url.run.app
python test_micstream_ser.py --file audio.wav
```

## Monitoring

### View Logs:

```bash
gcloud run services logs read well-bot-ser --region asia-south1
```

### View Metrics:

```bash
# Open Cloud Console
# Navigate to Cloud Run > well-bot-ser > Metrics
```

## Troubleshooting

### Service won't start:
- Check logs: `gcloud run services logs read well-bot-ser --region asia-south1`
- Verify environment variables are set correctly
- Check Supabase connection credentials

### Timeout errors:
- Increase timeout: `--timeout 600` (10 minutes)
- Check audio file size (Cloud Run has request size limits)

### Memory errors:
- **Lazy Loading**: Models are now loaded on first use (not at startup), reducing initial memory
- **CPU-only PyTorch**: Dockerfile uses CPU-only PyTorch builds to save memory
- **Memory Cleanup**: Models clean up memory after each inference
- If still failing, increase memory: `--memory 4Gi`
- Check logs for model loading messages to identify which model is causing issues

### Connection refused:
- Verify service is deployed: `gcloud run services list`
- Check service URL is correct
- Ensure `--allow-unauthenticated` flag is set

## Memory Optimizations

The service has been optimized to reduce memory usage:

1. **Lazy Model Loading**: Models are loaded only when first used, not at startup
   - Emotion recognition model loads on first emotion analysis request
   - Transcription model loads on first transcription request
   - Sentiment model loads on first sentiment analysis request

2. **CPU-only PyTorch**: Uses CPU-only PyTorch builds (smaller, saves memory)
   - Cloud Run doesn't provide GPUs, so GPU builds are unnecessary
   - Reduces Docker image size and memory footprint

3. **Memory Cleanup**: Automatic garbage collection after each inference
   - Cleans up temporary tensors and variables
   - Reduces memory accumulation over time

4. **Slim Base Image**: Uses `python:3.11-slim` instead of full Python image
   - Smaller base image reduces build time and memory

5. **Optimized Environment Variables**: 
   - Hugging Face cache set to `/tmp` (ephemeral storage)
   - PyTorch memory allocation limits configured

## Cost Optimization

- **Min Instances**: Set to 0 for cost savings (cold starts may occur)
- **Max Instances**: Limit based on expected load
- **CPU**: Can reduce to 1 for lower costs (slower processing)
- **Memory**: Minimum 2Gi recommended for ML models (can start with 2Gi due to optimizations)

## Security Notes

- Service role key has admin access - keep it secure
- Consider using Secret Manager for sensitive env vars:
  ```bash
  # Create secret
  echo -n "your-key" | gcloud secrets create supabase-service-key --data-file=-
  
  # Use in deployment
  --set-secrets SUPABASE_SERVICE_ROLE_KEY=supabase-service-key:latest
  ```

## Next Steps

1. Deploy the service
2. Get the service URL
3. Update edge app configuration with the URL
4. Test the connection
5. Monitor logs and metrics

