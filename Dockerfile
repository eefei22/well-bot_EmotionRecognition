# Dockerfile
FROM python:3.11

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 8080 (Cloud Run default) - also works with 8008 for local
EXPOSE 8081

# Run the application
# Cloud Run sets PORT=8080 automatically, we use that env var
# For local development, PORT defaults to 8008 if not set
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8081}"
