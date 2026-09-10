"""
Unit tests for the RSS collector stage.
Mocks feedparser so no real network calls are made.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import feedparser
import pytest

from techlens.ingestion.rss_collector import collect_source
from techlens.storage.models import Article, Source


def _make_source(db_session) -> Source:
    source = Source(
        id="test_feed",
        name="Test Feed",
        feed_url="https://example.com/feed.xml",
        home_url="https://example.com",
        source_type="rss",
    )
    db_session.add(source)
    db_session.commit()
    return source


def _parse_fixture_feed() -> object:
    """Parse the fixture RSS XML using feedparser (no network)."""
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_feed.xml"
    return feedparser.parse(fixture.read_text())


def test_collect_source_inserts_recent_articles(db_session):
    """Two recent articles in the fixture should be inserted; the old one filtered."""
    source = _make_source(db_session)
    parsed = _parse_fixture_feed()

    with patch("techlens.ingestion.rss_collector.feedparser.parse", return_value=parsed):
        count = collect_source(source, db_session)

    assert count == 2
    articles = db_session.query(Article).all()
    assert len(articles) == 2
    titles = {a.title for a in articles}
    assert "Building Production RAG Systems at Scale" in titles
    assert "MCP vs RAG vs Agents: Architecture Tradeoffs" in titles


def test_collect_source_skips_duplicate_url(db_session):
    """Collecting the same feed twice should not insert duplicates."""
    source = _make_source(db_session)
    parsed = _parse_fixture_feed()

    with patch("techlens.ingestion.rss_collector.feedparser.parse", return_value=parsed):
        first = collect_source(source, db_session)
        second = collect_source(source, db_session)

    assert first == 2
    assert second == 0  # all already in DB
    assert db_session.query(Article).count() == 2


def test_collect_source_filters_old_articles(db_session):
    """The old article (>7 days) in the fixture must not be inserted."""
    source = _make_source(db_session)
    parsed = _parse_fixture_feed()

    with patch("techlens.ingestion.rss_collector.feedparser.parse", return_value=parsed):
        collect_source(source, db_session)

    urls = {a.url for a in db_session.query(Article).all()}
    assert "https://example.com/old-article-filtered" not in urls


def test_collect_source_handles_feed_error(db_session):
    """A feedparser exception should increment failure_count and return 0."""
    source = _make_source(db_session)

    with patch("techlens.ingestion.rss_collector.feedparser.parse", side_effect=Exception("network error")):
        count = collect_source(source, db_session)

    assert count == 0
    db_session.refresh(source)
    assert source.failure_count == 1
