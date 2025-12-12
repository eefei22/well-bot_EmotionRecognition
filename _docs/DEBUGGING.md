# SER Service Debugging Guide

## Issue: Results showing "unknown" with 0% confidence

### Symptoms
- Items appear to skip queue and processing
- All results show "unknown" emotion with 0.0% confidence
- Results appear in dashboard but queue/processing columns are empty

### Root Causes

1. **Worker Thread Not Running**
   - Check server logs for: `"QueueManager worker loop started"`
   - If missing, startup event may have failed
   - Check logs for: `"Starting SER service background services..."`

2. **Emotion Recognition Failing**
   - TabTransformer model may not be loading correctly
   - Feature extraction may not match model expectations
   - Check logs for: `"Emotion recognition failed"` or `"Failed to load emotion model"`

3. **Model File Missing**
   - Verify `ser/ML_models/best_tabtransformer_7emo.pt` exists
   - Check logs for: `"Emotion recognition model not found"`

### Debugging Steps

1. **Check Server Logs**
   ```bash
   # Look for these log messages:
   - "QueueManager worker loop started" (worker running)
   - "Enqueued chunk for user..." (items being queued)
   - "Worker: Processing queued item..." (items being processed)
   - "Emotion recognition failed" (emotion model error)
   - "TabTransformer emotion model loaded successfully" (model loaded)
   ```

2. **Verify Model File**
   ```python
   import os
   model_path = "ser/ML_models/best_tabtransformer_7emo.pt"
   print(f"Model exists: {os.path.exists(model_path)}")
   print(f"Model path: {os.path.abspath(model_path)}")
   ```

3. **Test Model Loading**
   ```python
   from ser.emotion_recognition import _load_emotion_model
   try:
       model = _load_emotion_model()
       print(f"Model loaded: {type(model)}")
   except Exception as e:
       print(f"Model loading failed: {e}")
   ```

4. **Check Queue Status**
   ```python
   from ser.queue_manager import QueueManager
   qm = QueueManager.get_instance()
   print(f"Worker running: {qm.is_running()}")
   print(f"Queue size: {qm.get_queue_size()}")
   print(f"Queue items: {qm.get_queue_items()}")
   ```

### Common Fixes

1. **If worker thread not starting:**
   - Restart the server
   - Check for import errors in `main.py`
   - Verify `@app.on_event("startup")` is called

2. **If model not loading:**
   - Verify model file exists at correct path
   - Check file permissions
   - Verify PyTorch is installed: `pip install torch`

3. **If feature extraction fails:**
   - The TabTransformer model may expect different features
   - Check model documentation for expected input format
   - May need to adjust `_extract_features()` function

### Enhanced Logging

The code now includes enhanced logging:
- Queue operations: `logger.info()` when items are enqueued
- Worker operations: `logger.info()` when processing starts/completes
- Model loading: Detailed path and error logging
- Emotion recognition: Detailed error logging with stack traces

Check your server logs for these messages to diagnose the issue.

