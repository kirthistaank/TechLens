"""
Unit tests for the Phase 3 cross-source synthesizer.
Patches Kuzu's get_conn so no real graph DB is needed.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from techlens.knowledge_graph.synthesizer import (
    _build_articles_block,
    _overlap_fraction,
    synthesize_all,
    synthesize_cluster,
)
from techlens.storage.models import Article, ArticleStatus, Source, Synthesis, utcnow


def _make_source(db_session, sid: str) -> None:
    if not db_session.get(Source, sid):
        db_session.add(Source(id=sid, name=sid, feed_url="", home_url="https://example.com", source_type="rss"))
        db_session.commit()


def _make_summarized_article(db_session, url: str, source_id: str) -> Article:
    _make_source(db_session, source_id)
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=f"Article {url[-2:]}",
        publication=source_id,
        source_id=source_id,
        status=ArticleStatus.summarized,
        recommendation="READ",
        summary_what="Agent memory design emerged.",
        summary_why="Critical for production AI systems.",
        summary_architecture="Separate episodic from semantic stores.",
        concepts_extracted=True,
    )
    db_session.add(article)
    db_session.commit()
    return article


# ── _overlap_fraction ────────────────────────────────────────────────────────

def test_overlap_fraction_zero_when_no_overlap():
    assert _overlap_fraction([1, 2, 3], {4, 5, 6}) == 0.0


def test_overlap_fraction_full_overlap():
    assert _overlap_fraction([1, 2, 3], {1, 2, 3}) == 1.0


def test_overlap_fraction_partial():
    result = _overlap_fraction([1, 2, 3, 4], {2, 4})
    assert result == 0.5


def test_overlap_fraction_empty_new_ids():
    assert _overlap_fraction([], {1, 2, 3}) == 0.0


# ── _build_articles_block ────────────────────────────────────────────────────

def test_build_articles_block_contains_source_and_title(db_session):
    a = _make_summarized_article(db_session, "https://ex.com/z1", "src-a")
    block = _build_articles_block([a])
    assert "src-a" in block
    assert a.title in block
    assert "Agent memory design emerged." in block


def test_build_articles_block_separates_articles(db_session):
    a1 = _make_summarized_article(db_session, "https://ex.com/z2", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/z3", "src-b")
    block = _build_articles_block([a1, a2])
    assert "src-a" in block
    assert "src-b" in block
    # Two entries should be separated by a blank line
    assert "\n\n" in block


# ── synthesize_cluster ───────────────────────────────────────────────────────

def test_synthesize_cluster_creates_synthesis_record(db_session, mock_synthesis_llm):
    """synthesize_cluster should persist a Synthesis row with correct field values."""
    a1 = _make_summarized_article(db_session, "https://ex.com/s1", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/s2", "src-a")
    a3 = _make_summarized_article(db_session, "https://ex.com/s3", "src-b")

    synthesis = synthesize_cluster("Agent Memory", [a1, a2, a3], mock_synthesis_llm, db_session)

    assert synthesis is not None
    assert synthesis.topic == "Agent Memory In Production Systems"
    assert synthesis.article_count == 3
    assert synthesis.source_count == 2
    assert synthesis.is_active is True
    persisted_perspectives = json.loads(synthesis.unique_perspectives)
    assert len(persisted_perspectives) == 2


def test_synthesize_cluster_returns_none_on_llm_failure(db_session, mock_failing_llm):
    """When the LLM raises, synthesize_cluster should return None without writing anything."""
    a1 = _make_summarized_article(db_session, "https://ex.com/f1", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/f2", "src-b")
    a3 = _make_summarized_article(db_session, "https://ex.com/f3", "src-b")

    result = synthesize_cluster("Some Concept", [a1, a2, a3], mock_failing_llm, db_session)

    assert result is None
    assert db_session.query(Synthesis).count() == 0


# ── synthesize_all ───────────────────────────────────────────────────────────

@patch("techlens.storage.graph_store.get_conn")
def test_synthesize_all_creates_card_for_qualifying_cluster(mock_get_conn, db_session, mock_synthesis_llm):
    """synthesize_all should produce one Synthesis when a concept has 3+ articles from 2+ sources."""
    a1 = _make_summarized_article(db_session, "https://ex.com/q1", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/q2", "src-a")
    a3 = _make_summarized_article(db_session, "https://ex.com/q3", "src-b")

    conn = MagicMock()
    mock_get_conn.return_value = conn
    rows = [
        ["Agent Memory", a1.id, "src-a"],
        ["Agent Memory", a2.id, "src-a"],
        ["Agent Memory", a3.id, "src-b"],
    ]
    result_mock = MagicMock()
    result_mock.has_next.side_effect = [True, True, True, False]
    result_mock.get_next.side_effect = rows
    conn.execute.return_value = result_mock

    count = synthesize_all(db_session, mock_synthesis_llm)

    assert count == 1
    assert db_session.query(Synthesis).count() == 1


@patch("techlens.storage.graph_store.get_conn")
def test_synthesize_all_skips_cluster_under_threshold(mock_get_conn, db_session, mock_synthesis_llm):
    """Clusters with < 3 articles or only 1 source should not produce a Synthesis."""
    a1 = _make_summarized_article(db_session, "https://ex.com/u1", "src-x")
    a2 = _make_summarized_article(db_session, "https://ex.com/u2", "src-x")

    conn = MagicMock()
    mock_get_conn.return_value = conn
    rows = [
        ["Niche Topic", a1.id, "src-x"],
        ["Niche Topic", a2.id, "src-x"],
    ]
    result_mock = MagicMock()
    result_mock.has_next.side_effect = [True, True, False]
    result_mock.get_next.side_effect = rows
    conn.execute.return_value = result_mock

    count = synthesize_all(db_session, mock_synthesis_llm)

    assert count == 0
    assert db_session.query(Synthesis).count() == 0


@patch("techlens.storage.graph_store.get_conn")
def test_synthesize_all_skips_already_covered_cluster(mock_get_conn, db_session, mock_synthesis_llm):
    """Clusters where >50% of article IDs are already in an active Synthesis should be skipped."""
    a1 = _make_summarized_article(db_session, "https://ex.com/v1", "src-a")
    a2 = _make_summarized_article(db_session, "https://ex.com/v2", "src-a")
    a3 = _make_summarized_article(db_session, "https://ex.com/v3", "src-b")

    # Pre-existing synthesis covers all three articles
    existing = Synthesis(
        topic="Already Done",
        summary="Covered.",
        unique_perspectives=json.dumps(["A", "B"]),
        key_insight="Already known.",
        source_count=2,
        article_count=3,
        concepts=json.dumps(["Agent Memory"]),
        article_ids=json.dumps([a1.id, a2.id, a3.id]),
        generated_at=utcnow(),
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    conn = MagicMock()
    mock_get_conn.return_value = conn
    rows = [
        ["Agent Memory", a1.id, "src-a"],
        ["Agent Memory", a2.id, "src-a"],
        ["Agent Memory", a3.id, "src-b"],
    ]
    result_mock = MagicMock()
    result_mock.has_next.side_effect = [True, True, True, False]
    result_mock.get_next.side_effect = rows
    conn.execute.return_value = result_mock

    count = synthesize_all(db_session, mock_synthesis_llm)

    assert count == 0
    assert db_session.query(Synthesis).count() == 1  # only the pre-existing one


@patch("techlens.storage.graph_store.get_conn")
def test_synthesize_all_deactivates_stale_records(mock_get_conn, db_session, mock_synthesis_llm):
    """Synthesis cards older than 14 days should be deactivated."""
    stale_time = datetime.now(timezone.utc) - timedelta(days=20)
    stale = Synthesis(
        topic="Old Synthesis",
        summary="Old.",
        unique_perspectives=json.dumps([]),
        key_insight="Old insight.",
        source_count=2,
        article_count=3,
        concepts=json.dumps(["Old Concept"]),
        article_ids=json.dumps([]),
        generated_at=stale_time,
        is_active=True,
    )
    db_session.add(stale)
    db_session.commit()

    conn = MagicMock()
    mock_get_conn.return_value = conn
    result_mock = MagicMock()
    result_mock.has_next.return_value = False
    conn.execute.return_value = result_mock

    synthesize_all(db_session, mock_synthesis_llm)

    db_session.refresh(stale)
    assert stale.is_active is False
