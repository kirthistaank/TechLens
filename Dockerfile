# TechLens backend Docker image — Python 3.11 slim
FROM python:3.11.16-slim

WORKDIR /app

# Install uv for fast, deterministic dependency resolution
RUN pip install --no-cache-dir uv>=0.1.0

# Copy dependency files first (cached layer if no changes)
COPY pyproject.toml .
# uv.lock pinned all versions; next build reuses cache
RUN uv sync --frozen

# Copy application source (invalidates above cache only if src/ changes)
COPY src/ src/
COPY config/ config/
COPY frontend/dist/ frontend/dist/

# Create directories for persistent storage
RUN mkdir -p /data/db /data/chroma && \
    chmod -R 777 /data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    UV_CACHE_DIR="/tmp/.uv-cache"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/digest/daily')" || exit 1

# Expose port
EXPOSE 8000

# Run Uvicorn server
CMD ["uvicorn", "techlens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
