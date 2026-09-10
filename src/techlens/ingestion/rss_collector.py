"""
RSS feed collector — Stage 1 of the TechLens pipeline.
Reads sources from sources.yaml, fetches each RSS feed, and inserts new articles
into the database. Skips articles whose URL was already seen (by URL hash).
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import yaml
from sqlalchemy.orm import Session

from techlens.storage.models import Article, Source

logger = logging.getLogger(__name__)

_SOURCES_PATH = Path(__file__).parents[3] / "config" / "sources.yaml"


def load_sources_from_yaml(session: Session) -> None:
    """
    Sync sources.yaml into the DB as an upsert.
    Handles rss, substack, and web source types.
    Extra fields (listing_url, link_pattern) are stored as dynamic attributes
    on the Source object for use by the web collector — they are not persisted
    to the DB but re-attached each time sources are loaded.
    """
    with open(_SOURCES_PATH) as f:
        data = yaml.safe_load(f)

    import json

    for entry in data.get("sources", []):
        source = session.get(Source, entry["id"])
        if source is None:
            source = Source(id=entry["id"])
            session.add(source)

        source.name = entry["name"]
        source.home_url = entry["home_url"]
        source.source_type = entry.get("source_type", "rss")
        source.priority = entry.get("priority", 3)
        source.categories = json.dumps(entry.get("categories", []))
        source.polling_frequency_minutes = entry.get("polling_frequency_minutes", 360)
        source.enabled = entry.get("enabled", True)

        # RSS / substack fields
        source.feed_url = entry.get("feed_url", "")

        # Web scraper fields — stored as transient attributes, not DB columns
        source.listing_url = entry.get("listing_url", "")
        source.link_pattern = entry.get("link_pattern", "")

    session.commit()
    logger.info("Sources synced from YAML")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def collect_source(source: Source, session: Session) -> int:
    """
    Fetch RSS feed for a source and insert articles published within the lookback window.

    Skips articles older than settings.article_lookback_days and any URLs already in the DB.

    Args:
        source: Enabled Source record with source_type rss or substack.
        session: Active SQLAlchemy session.

    Returns:
        Number of new articles inserted.
    """
    from techlens.config import settings

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.article_lookback_days)

    logger.info("Collecting %s (lookback: %d days)", source.name, settings.article_lookback_days)
    try:
        feed = feedparser.parse(source.feed_url)
    except Exception as exc:
        logger.error("Failed to fetch feed %s: %s", source.feed_url, exc)
        source.failure_count += 1
        session.commit()
        return 0

    new_count = 0
    skipped_old = 0
    for entry in feed.entries:
        url = entry.get("link", "").strip()
        if not url:
            continue

        # Parse published date and apply lookback filter
        published_at: datetime | None = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        if published_at and published_at < cutoff:
            skipped_old += 1
            continue

        uhash = _url_hash(url)
        if session.query(Article).filter_by(url_hash=uhash).first():
            continue

        article = Article(
            url=url,
            url_hash=uhash,
            title=entry.get("title", "Untitled")[:500],
            author=entry.get("author", None),
            publication=source.name,
            source_id=source.id,
            published_at=published_at,
            raw_content=entry.get("summary", None),
        )
        session.add(article)
        new_count += 1

    source.last_polled_at = datetime.now(timezone.utc)
    source.failure_count = 0
    session.commit()
    logger.info(
        "Collected %d new articles from %s (%d skipped — older than %d days)",
        new_count, source.name, skipped_old, settings.article_lookback_days,
    )
    return new_count


def collect_all(session: Session) -> int:
    """
    Run RSS collection for all enabled rss and substack sources.
    Web-type sources are handled separately by web_collector.collect_all_web().
    """
    sources = (
        session.query(Source)
        .filter(Source.enabled == True, Source.source_type.in_(["rss", "substack"]))  # noqa: E712
        .all()
    )
    total = sum(collect_source(s, session) for s in sources)
    logger.info("RSS collection complete — %d new articles total", total)
    return total
