# =====================================================================
# Multi-stage-friendly, small production image for the Flask backend.
# Build:  docker build -f docker/Dockerfile -t hobby-tracker .
# Run:    docker run -p 8080:8080 --env-file .env hobby-tracker
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application code
COPY backend/ ./backend/
COPY cloud/ ./cloud/
COPY analytics/ ./analytics/
COPY frontend/ ./frontend/

# Writable directory for the SQLite fallback + local uploads
RUN mkdir -p /app/backend/data /app/backend/uploads

# Run as a non-root user (security best practice)
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health').status==200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "60", "backend.app:app"]