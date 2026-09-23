# TechLens backend Docker image
FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml pyproject.toml
COPY src/ src/
COPY frontend/dist/ frontend/dist/

# Install dependencies using uv
RUN uv sync

# Create directories for persistent storage
RUN mkdir -p /data/db /data/chroma && \
    chmod -R 777 /data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run Uvicorn server
CMD ["uvicorn", "techlens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
