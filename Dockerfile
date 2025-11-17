# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Set environment variables to reduce memory usage
ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/tmp/.cache/huggingface
ENV HF_HOME=/tmp/.cache/huggingface
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with memory optimizations
# Install CPU-only PyTorch to save memory (Cloud Run doesn't have GPUs)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.3.0 torchaudio==2.3.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge

# Copy application code
COPY . .

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Run the application
# Cloud Run sets PORT=8080 automatically, we use that env var
# For local development, PORT defaults to 8008 if not set
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8008}"
