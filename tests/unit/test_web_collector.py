"""
Unit tests for the web listing collector.
Mocks httpx so no real network calls are made.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from techlens.ingestion.web_collector import _extract_links, collect_web_source
from techlens.storage.models import Article, Source

_FIXTURE_HTML = (Path(__file__).parents[1] / "fixtures" / "sample_listing.html").read_text()
_LINK_PATTERN = r'href="(/the-batch/[a-z0-9][a-z0-9-]*-[a-z0-9][a-z0-9-]*)"'
_BASE_URL = "https://www.deeplearning.ai"


def _make_web_source(db_session) -> Source:
    source = Source(
        id="deeplearning_ai_batch",
        name="The Batch",
        feed_url="",
        home_url="https://www.deeplearning.ai/the-batch/",
        source_type="web",
        listing_url="https://www.deeplearning.ai/the-batch/tag/letters/",
        link_pattern=_LINK_PATTERN,
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_extract_links_returns_unique_article_urls():
    """Should return 3 unique article URLs, deduplicating the repeated link."""
    links = _extract_links(_FIXTURE_HTML, _BASE_URL, _LINK_PATTERN)
    assert len(links) == 3
    assert all("deeplearning.ai" in l for l in links)


def test_extract_links_excludes_nav_pages():
    """Single-word slugs like /the-batch/about must not match."""
    links = _extract_links(_FIXTURE_HTML, _BASE_URL, _LINK_PATTERN)
    assert not any(l.endswith("/about") or l.endswith("/search") for l in links)


def test_collect_web_source_inserts_stubs(db_session):
    """Should insert article stubs for each discovered URL."""
    source = _make_web_source(db_session)
    mock_resp = MagicMock()
    mock_resp.text = _FIXTURE_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("techlens.ingestion.web_collector.httpx.get", return_value=mock_resp):
        count = collect_web_source(source, db_session)

    assert count == 3
    assert db_session.query(Article).count() == 3


def test_collect_web_source_skips_existing_urls(db_session):
    """Running the collector twice should not insert duplicate stubs."""
    source = _make_web_source(db_session)
    mock_resp = MagicMock()
    mock_resp.text = _FIXTURE_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("techlens.ingestion.web_collector.httpx.get", return_value=mock_resp):
        first = collect_web_source(source, db_session)
        second = collect_web_source(source, db_session)

    assert first == 3
    assert second == 0


def test_collect_web_source_handles_http_error(db_session):
    """An httpx exception should increment failure_count and return 0."""
    source = _make_web_source(db_session)

    with patch("techlens.ingestion.web_collector.httpx.get", side_effect=Exception("timeout")):
        count = collect_web_source(source, db_session)

    assert count == 0
    db_session.refresh(source)
    assert source.failure_count == 1
