"""
FastAPI application entry point for TechLens.
Initialises the database, starts the background scheduler, configures CORS for the React
dev server, mounts API routes, and serves the React build as static files in production.
"""

import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from techlens.api.limiter import limiter

from techlens.api.routes import router
from techlens.config import settings
from techlens.scheduling.scheduler import start_scheduler, stop_scheduler
from techlens.storage.db import init_db
from techlens.storage.graph_store import init_graph

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_graph()
    start_scheduler()
    logger.info("TechLens started")
    yield
    stop_scheduler()
    logger.info("TechLens stopped")


app = FastAPI(title="TechLens", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",              # Vite dev server (local development)
        "http://localhost:3000",              # Alternative dev server (local development)
        "http://localhost:8001",              # Python http.server (local testing)
        "http://129.146.58.128:8000",         # TechLens backend (self-requests)
        "https://kirthistaank.github.io",     # GitHub Pages landing page
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve React build in production
_static_dir = Path(__file__).parents[3] / "frontend" / "dist"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
