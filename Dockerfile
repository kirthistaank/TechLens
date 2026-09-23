# Multi-stage build for TechLens backend
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml pyproject.toml

# Create virtual environment and install dependencies
RUN uv venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy source code
COPY src/ src/
COPY frontend/dist/ frontend/dist/

# Create directories for persistent storage
RUN mkdir -p /data/db /data/chroma && \
    chmod -R 777 /data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run Uvicorn server
CMD ["uvicorn", "techlens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
