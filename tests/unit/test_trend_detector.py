"""
Unit tests for the Phase 3 trend detector.
Patches Kuzu graph_store calls and controls article/source cluster data directly.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from techlens.knowledge_graph.trend_detector import _trend_already_active, detect_trends
from techlens.storage.models import Article, ArticleStatus, Source, Trend, utcnow


def _make_source(db_session, sid: str) -> None:
    if not db_session.get(Source, sid):
        db_session.add(Source(id=sid, name=sid, feed_url="", home_url="https://example.com", source_type="rss"))
        db_session.commit()


def _make_summarized_article(db_session, url: str, source_id: str, days_ago: int = 3) -> Article:
    _make_source(db_session, source_id)
    retrieved = datetime.now(timezone.utc) - timedelta(days=days_ago)
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=f"Article from {source_id}",
        publication=source_id,
        source_id=source_id,
        status=ArticleStatus.summarized,
        recommendation="READ",
        summary_what="Something happened.",
        retrieved_at=retrieved,
        concepts_extracted=True,
    )
    db_session.add(article)
    db_session.commit()
    return article


# ── _trend_already_active ────────────────────────────────────────────────────

def test_trend_already_active_returns_false_when_no_trends(db_session):
    """No existing trends → always returns False."""
    assert _trend_already_active(db_session, "Agent Memory", 7) is False


def test_trend_already_active_returns_true_for_recent_matching_trend(db_session):
    """A fresh active trend covering the concept should suppress a duplicate."""
    trend = Trend(
        name="Agent Memory Trend",
        summary="Memory is hot.",
        confidence="high",
        window_days=7,
        article_count=3,
        source_count=2,
        concepts=json.dumps(["Agent Memory"]),
        detected_at=utcnow(),
        is_active=True,
    )
    db_session.add(trend)
    db_session.commit()

    assert _trend_already_active(db_session, "Agent Memory", 7) is True


def test_trend_already_active_ignores_inactive_trend(db_session):
    """An inactive (deactivated) trend should not suppress detection."""
    trend = Trend(
        name="Old Trend",
        summary="Old.",
        confidence="low",
        window_days=7,
        article_count=3,
        source_count=2,
        concepts=json.dumps(["Agent Memory"]),
        detected_at=utcnow(),
        is_active=False,
    )
    db_session.add(trend)
    db_session.commit()

    assert _trend_already_active(db_session, "Agent Memory", 7) is False


def test_trend_already_active_ignores_old_trend(db_session):
    """A trend older than the dedup window (7 days) should not suppress detection."""
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    trend = Trend(
        name="Old Active Trend",
        summary="Old but active.",
        confidence="medium",
        window_days=7,
        article_count=3,
        source_count=2,
        concepts=json.dumps(["Agent Memory"]),
        detected_at=old_time,
        is_active=True,
    )
    db_session.add(trend)
    db_session.commit()

    assert _trend_already_active(db_session, "Agent Memory", 7) is False


# ── detect_trends ────────────────────────────────────────────────────────────

@patch("techlens.knowledge_graph.trend_detector.get_article_ids_for_concept")
@patch("techlens.knowledge_graph.trend_detector.get_concepts_in_window")
def test_detect_trends_creates_trend_for_qualifying_cluster(
    mock_get_concepts, mock_get_ids, db_session, mock_trend_llm,
):
    """A concept with 3 articles from 2 sources should produce one new Trend record."""
    a1 = _make_summarized_article(db_session, "https://ex.com/a1", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/a2", "src-a")
    a3 = _make_summarized_article(db_session, "https://ex.com/a3", "src-b")

    # Return cluster only for the 7-day window; empty for the 30-day window.
    mock_get_concepts.side_effect = [
        [{"name": "Agent Memory", "concept_type": "architecture_pattern", "article_count": 3, "source_count": 2}],
        [],
    ]
    mock_get_ids.return_value = [a1.id, a2.id, a3.id]

    new_count = detect_trends(db_session, mock_trend_llm)

    assert new_count == 1
    trend = db_session.query(Trend).first()
    assert trend is not None
    assert trend.is_active is True
    assert trend.confidence == "high"
    assert trend.article_count == 3
    assert trend.source_count == 2


@patch("techlens.knowledge_graph.trend_detector.get_article_ids_for_concept")
@patch("techlens.knowledge_graph.trend_detector.get_concepts_in_window")
def test_detect_trends_skips_unqualified_cluster(
    mock_get_concepts, mock_get_ids, db_session, mock_trend_llm,
):
    """A concept with only 1 article from 1 source does not qualify."""
    _make_summarized_article(db_session, "https://ex.com/c1", "src-x")

    mock_get_concepts.return_value = [
        {"name": "Obscure Topic", "concept_type": "concept", "article_count": 1, "source_count": 1}
    ]

    new_count = detect_trends(db_session, mock_trend_llm)

    assert new_count == 0
    assert db_session.query(Trend).count() == 0


@patch("techlens.knowledge_graph.trend_detector.get_article_ids_for_concept")
@patch("techlens.knowledge_graph.trend_detector.get_concepts_in_window")
def test_detect_trends_deduplicates_existing_trend(
    mock_get_concepts, mock_get_ids, db_session, mock_trend_llm,
):
    """When an active trend for the concept already exists, detect_trends should not create a duplicate."""
    a1 = _make_summarized_article(db_session, "https://ex.com/d1", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/d2", "src-a")
    a3 = _make_summarized_article(db_session, "https://ex.com/d3", "src-b")

    existing = Trend(
        name="Rising Agent Memory Trend",
        summary="Already known.",
        confidence="high",
        window_days=7,
        article_count=3,
        source_count=2,
        concepts=json.dumps(["Agent Memory"]),
        detected_at=utcnow(),
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    mock_get_concepts.side_effect = [
        [{"name": "Agent Memory", "concept_type": "architecture_pattern", "article_count": 3, "source_count": 2}],
        [],
    ]
    mock_get_ids.return_value = [a1.id, a2.id, a3.id]

    new_count = detect_trends(db_session, mock_trend_llm)

    assert new_count == 0
    assert db_session.query(Trend).count() == 1  # only the pre-existing one


@patch("techlens.knowledge_graph.trend_detector.get_article_ids_for_concept")
@patch("techlens.knowledge_graph.trend_detector.get_concepts_in_window")
def test_detect_trends_deactivates_stale_trends(
    mock_get_concepts, mock_get_ids, db_session, mock_trend_llm,
):
    """Trends older than 35 days should be deactivated when detect_trends runs."""
    stale_time = datetime.now(timezone.utc) - timedelta(days=40)
    stale = Trend(
        name="Old Trend",
        summary="Very old.",
        confidence="low",
        window_days=7,
        article_count=2,
        source_count=1,
        concepts=json.dumps(["Old Concept"]),
        detected_at=stale_time,
        is_active=True,
    )
    db_session.add(stale)
    db_session.commit()

    mock_get_concepts.return_value = []

    detect_trends(db_session, mock_trend_llm)

    db_session.refresh(stale)
    assert stale.is_active is False
