"""
Pydantic response and request schemas for the TechLens API.
These are the data shapes that cross the boundary between the FastAPI layer and callers.
Includes Phase 3 schemas: TrendOut, ConceptOut, SynthesisOut, and KnowledgeMapOut.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ArticleOut(BaseModel):
    id: int
    title: str
    url: str
    source: str
    publication: str
    score: float | None
    recommendation: str | None
    score_rationale: str | None
    what_happened: str | None
    why_it_matters: str | None
    technical_insights: list[str]
    architecture_implication: str | None
    tradeoffs: str | None
    estimated_reading_minutes: int | None
    categories: list[str]
    published_at: datetime | None
    is_duplicate: bool
    is_archived: bool
    is_saved: bool
    is_important: bool
    opened_at: datetime | None
    user_rating: str | None

    model_config = {"from_attributes": True}


class RateRequest(BaseModel):
    rating: str | None  # "up" | "down" | None to clear


class SourceOut(BaseModel):
    id: str
    name: str
    feed_url: str
    home_url: str
    source_type: str
    priority: int
    categories: list[str]
    enabled: bool
    last_polled_at: datetime | None
    failure_count: int

    model_config = {"from_attributes": True}


class DigestOut(BaseModel):
    date: str
    generated_at: str
    total_collected: int
    total_scored: int
    items: list[dict[str, Any]]


class SourceCreate(BaseModel):
    id: str
    name: str
    feed_url: str
    home_url: str
    source_type: str = "rss"
    priority: int = 3
    categories: list[str] = []
    polling_frequency_minutes: int = 360
    enabled: bool = True


class PipelineStatus(BaseModel):
    ollama_available: bool
    total_articles: int
    pending: int
    extracted: int
    embedded: int
    scored: int
    summarized: int
    ignored: int
    failed: int


# --- Phase 3: Knowledge Graph ---

class TrendOut(BaseModel):
    """Serialised trend card returned by /api/trends."""

    id: int
    name: str
    summary: str
    confidence: str  # high | medium | low
    window_days: int
    article_count: int
    source_count: int
    # Deserialised from JSON column so the frontend receives a typed list
    concepts: list[str]
    detected_at: datetime

    model_config = {"from_attributes": True}


class ConceptOut(BaseModel):
    """Serialised concept stat returned by /api/concepts/top. Sourced from Kuzu, not SQLite."""

    name: str
    concept_type: str
    article_count: int
    source_count: int
    first_seen_at: str   # ISO string from Kuzu
    last_seen_at: str


class SynthesisOut(BaseModel):
    """Serialised synthesis card returned by /api/synthesis. JSON columns are deserialised."""

    id: int
    topic: str
    summary: str
    unique_perspectives: list[str]
    key_insight: str
    source_count: int
    article_count: int
    concepts: list[str]
    article_ids: list[int]
    generated_at: datetime

    model_config = {"from_attributes": True}


class ConceptKnowledgeItem(BaseModel):
    """Per-concept knowledge state for the /api/knowledge/map endpoint."""

    name: str
    concept_type: str
    article_count: int
    source_count: int
    read_count: int
    # "seen" if no article opened yet, "read" if at least one opened
    state: str


class KnowledgeMapOut(BaseModel):
    """Full knowledge map response: top concepts with read/seen state plus tier1 gaps."""

    concepts: list[ConceptKnowledgeItem]
    tier1_gaps: list[str]
    total_seen: int
    total_read: int
