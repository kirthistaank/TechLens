"""
SQLAlchemy ORM models for TechLens: Source, Article, Digest, Trend, TrendArticle, and Synthesis.
Phase 3 concept/graph data lives in Kuzu (graph_store.py), not here.
Enums for article status, recommendation, and source type are also defined here.
"""

import json
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceType(str, Enum):
    rss = "rss"
    substack = "substack"
    medium = "medium"
    website = "website"


class ArticleStatus(str, Enum):
    pending = "pending"
    extracted = "extracted"
    scored = "scored"
    summarized = "summarized"
    ignored = "ignored"
    failed = "failed"


class Recommendation(str, Enum):
    READ = "READ"
    SKIM = "SKIM"
    IGNORE = "IGNORE"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    feed_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    home_url: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, default="rss")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    categories: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    polling_frequency_minutes: Mapped[int] = mapped_column(Integer, default=360)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Web scraper fields (used when source_type='web')
    listing_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    link_pattern: Mapped[str] = mapped_column(String, nullable=False, default="")

    articles: Mapped[list["Article"]] = relationship("Article", back_populates="source")

    def get_categories(self) -> list[str]:
        return json.loads(self.categories)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    url_hash: Mapped[str] = mapped_column(String, index=True, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    publication: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)

    # Classification + scoring
    categories: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    score_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Summary fields
    summary_what: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_why: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_technical: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    summary_architecture: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_tradeoffs: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_reading_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Dedup
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    canonical_article_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("articles.id"), nullable=True
    )

    # User actions
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_rating: Mapped[str | None] = mapped_column(String, nullable=True)  # "up" | "down" | None

    status: Mapped[str] = mapped_column(String, default=ArticleStatus.pending)
    # Phase 3: tracks whether concept extraction has run for this article
    concepts_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped["Source"] = relationship("Source", back_populates="articles")

    def get_categories(self) -> list[str]:
        return json.loads(self.categories) if self.categories else []

    def get_technical_insights(self) -> list[str]:
        return json.loads(self.summary_technical) if self.summary_technical else []


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    digest_type: Mapped[str] = mapped_column(String, default="daily")
    date: Mapped[str] = mapped_column(String, index=True)  # YYYY-MM-DD
    content: Mapped[str] = mapped_column(Text)  # JSON
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Phase 3: Trends (concept graph lives in Kuzu — see storage/graph_store.py) ---

class Trend(Base):
    """An LLM-synthesised trend card derived from concept co-occurrence across articles."""

    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # high / medium / low
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    # 7 or 30 — the detection window in days
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    # JSON list of concept names that define this trend
    concepts: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    article_links: Mapped[list["TrendArticle"]] = relationship(
        "TrendArticle", back_populates="trend"
    )


class TrendArticle(Base):
    """Evidence articles supporting a trend."""

    __tablename__ = "trend_articles"
    __table_args__ = (UniqueConstraint("trend_id", "article_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trend_id: Mapped[int] = mapped_column(Integer, ForeignKey("trends.id"), nullable=False)
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey("articles.id"), nullable=False)

    trend: Mapped["Trend"] = relationship("Trend", back_populates="article_links")


# --- Phase 3: Cross-Source Synthesis ---

class Synthesis(Base):
    """
    LLM-generated synthesis card produced when 3+ articles from 2+ sources cover
    the same concept. Stores a distilled summary, unique per-source perspectives,
    and the key architecture takeaway. Constituent article IDs stored as JSON.
    """

    __tablename__ = "syntheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # LLM-generated short label, e.g. "OpenAI o3 Architecture Release"
    topic: Mapped[str] = mapped_column(String, nullable=False)
    # 2-3 sentence synthesis across all sources
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON list of strings — what each source adds uniquely
    unique_perspectives: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # One-sentence architecture takeaway
    key_insight: Mapped[str] = mapped_column(Text, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # JSON list of concept names that define this cluster
    concepts: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # JSON list of int article IDs
    article_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
