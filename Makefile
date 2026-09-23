# Makefile for TechLens — common dev commands.
# Run `make help` to see all targets.

.PHONY: help backend frontend dev install pipeline

help:
	@echo "TechLens dev commands:"
	@echo "  make install    — install all Python dependencies"
	@echo "  make backend    — start FastAPI backend on :8005"
	@echo "  make frontend   — start React dev server on :5173"
	@echo "  make pipeline   — run the pipeline once manually"

## Install Python dependencies via uv
install:
	uv sync

## Start FastAPI backend with hot-reload
backend:
	PYTHONPATH=src uv run uvicorn techlens.api.main:app --reload --port 8005

## Start React/Vite frontend dev server
frontend:
	cd frontend && npm run dev

## Trigger a one-shot pipeline run (collect → score → summarize → digest → email)
pipeline:
	PYTHONPATH=src uv run python -c "from techlens.scheduling.scheduler import run_pipeline; run_pipeline()"
