"""
Phase 3 integration smoke test.
Starts from already-summarized articles in SQLite and runs the full Phase 3 pipeline:
  extract_all → detect_trends → synthesize_all
All Kuzu graph_store calls are mocked — no real Kuzu DB required.
"""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from techlens.knowledge_graph.extractor import extract_all
from techlens.knowledge_graph.trend_detector import detect_trends
from techlens.knowledge_graph.synthesizer import synthesize_all
from techlens.storage.models import Article, ArticleStatus, Source, Synthesis, Trend


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def two_sources(db_session):
    """Two distinct RSS sources for multi-source cluster tests."""
    db_session.add(Source(id="src-alpha", name="Alpha Blog", feed_url="", home_url="https://alpha.com", source_type="rss"))
    db_session.add(Source(id="src-beta", name="Beta Blog", feed_url="", home_url="https://beta.com", source_type="rss"))
    db_session.commit()


def _make_article(db_session, url: str, source_id: str) -> Article:
    a = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=f"Article {url[-2:]}",
        publication=source_id,
        source_id=source_id,
        status=ArticleStatus.summarized,
        recommendation="READ",
        summary_what="Agent memory design patterns are becoming standard.",
        summary_why="Production agents require persistent, structured memory.",
        summary_architecture="Separate episodic from semantic memory stores.",
        summary_technical=json.dumps(["Bi-encoder outperforms cross-encoder at scale"]),
        concepts_extracted=False,
    )
    db_session.add(a)
    db_session.commit()
    return a


# ── Tests ─────────────────────────────────────────────────────────────────────

@patch("techlens.knowledge_graph.extractor.refresh_source_counts")
@patch("techlens.knowledge_graph.extractor.link_article_concept", return_value=True)
@patch("techlens.knowledge_graph.extractor.upsert_concept")
@patch("techlens.knowledge_graph.extractor.upsert_article_node")
@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_all_phase3_stage(
    mock_get_conn, mock_upsert_node, mock_upsert_concept, mock_link, mock_refresh,
    db_session, two_sources, mock_extractor_llm,
):
    """extract_all should process all unextracted summarized READ articles."""
    mock_get_conn.return_value = MagicMock()

    a1 = _make_article(db_session, "https://alpha.com/p1", "src-alpha")
    a2 = _make_article(db_session, "https://beta.com/p2", "src-beta")
    a3 = _make_article(db_session, "https://alpha.com/p3", "src-alpha")

    processed = extract_all(db_session, mock_extractor_llm)

    assert processed == 3
    for article in [a1, a2, a3]:
        db_session.refresh(article)
        assert article.concepts_extracted is True

    mock_refresh.assert_called_once()


@patch("techlens.knowledge_graph.trend_detector.get_article_ids_for_concept")
@patch("techlens.knowledge_graph.trend_detector.get_concepts_in_window")
def test_detect_trends_phase3_stage(
    mock_get_concepts, mock_get_ids, db_session, two_sources, mock_trend_llm,
):
    """detect_trends should write a Trend record for a qualifying cross-source concept cluster."""
    a1 = _make_article(db_session, "https://alpha.com/t1", "src-alpha")
    a2 = _make_article(db_session, "https://alpha.com/t2", "src-alpha")
    a3 = _make_article(db_session, "https://beta.com/t3", "src-beta")
    for a in [a1, a2, a3]:
        a.concepts_extracted = True
    db_session.commit()

    mock_get_concepts.side_effect = [
        [{"name": "Agent Memory", "concept_type": "architecture_pattern", "article_count": 3, "source_count": 2}],
        [],
    ]
    mock_get_ids.return_value = [a1.id, a2.id, a3.id]

    new_trends = detect_trends(db_session, mock_trend_llm)

    assert new_trends == 1
    trend = db_session.query(Trend).first()
    assert trend.is_active is True
    assert trend.article_count == 3
    assert "Agent Memory" in json.loads(trend.concepts)


@patch("techlens.storage.graph_store.get_conn")
def test_synthesize_all_phase3_stage(mock_get_conn, db_session, two_sources, mock_synthesis_llm):
    """synthesize_all should produce a Synthesis record for a 3-article, 2-source concept cluster."""
    a1 = _make_article(db_session, "https://alpha.com/s1", "src-alpha")
    a2 = _make_article(db_session, "https://alpha.com/s2", "src-alpha")
    a3 = _make_article(db_session, "https://beta.com/s3", "src-beta")

    conn = MagicMock()
    mock_get_conn.return_value = conn
    rows = [
        ["Agent Memory", a1.id, "src-alpha"],
        ["Agent Memory", a2.id, "src-alpha"],
        ["Agent Memory", a3.id, "src-beta"],
    ]
    result_mock = MagicMock()
    result_mock.has_next.side_effect = [True, True, True, False]
    result_mock.get_next.side_effect = rows
    conn.execute.return_value = result_mock

    new_syntheses = synthesize_all(db_session, mock_synthesis_llm)

    assert new_syntheses == 1
    synthesis = db_session.query(Synthesis).first()
    assert synthesis.is_active is True
    assert synthesis.source_count == 2
    assert synthesis.article_count == 3
    perspectives = json.loads(synthesis.unique_perspectives)
    assert len(perspectives) >= 1


@patch("techlens.storage.graph_store.get_conn")
@patch("techlens.knowledge_graph.trend_detector.get_article_ids_for_concept")
@patch("techlens.knowledge_graph.trend_detector.get_concepts_in_window")
@patch("techlens.knowledge_graph.extractor.refresh_source_counts")
@patch("techlens.knowledge_graph.extractor.link_article_concept", return_value=True)
@patch("techlens.knowledge_graph.extractor.upsert_concept")
@patch("techlens.knowledge_graph.extractor.upsert_article_node")
@patch("techlens.knowledge_graph.extractor.get_conn")
def test_full_phase3_pipeline(
    mock_ext_conn, mock_upsert_node, mock_upsert_concept, mock_link, mock_refresh,
    mock_get_concepts, mock_get_ids, mock_synth_conn,
    db_session, two_sources,
    mock_extractor_llm, mock_trend_llm, mock_synthesis_llm,
):
    """
    Full Phase 3 smoke test: extract_all → detect_trends → synthesize_all
    on the same set of articles. All Kuzu calls mocked.
    """
    mock_ext_conn.return_value = MagicMock()

    a1 = _make_article(db_session, "https://alpha.com/e1", "src-alpha")
    a2 = _make_article(db_session, "https://alpha.com/e2", "src-alpha")
    a3 = _make_article(db_session, "https://beta.com/e3", "src-beta")

    # Stage 1: concept extraction
    processed = extract_all(db_session, mock_extractor_llm)
    assert processed == 3

    # Stage 2: trend detection
    mock_get_concepts.side_effect = [
        [{"name": "Agent Memory", "concept_type": "architecture_pattern", "article_count": 3, "source_count": 2}],
        [],
    ]
    mock_get_ids.return_value = [a1.id, a2.id, a3.id]
    new_trends = detect_trends(db_session, mock_trend_llm)
    assert new_trends == 1

    # Stage 3: synthesis
    conn = MagicMock()
    mock_synth_conn.return_value = conn
    rows = [
        ["Agent Memory", a1.id, "src-alpha"],
        ["Agent Memory", a2.id, "src-alpha"],
        ["Agent Memory", a3.id, "src-beta"],
    ]
    result_mock = MagicMock()
    result_mock.has_next.side_effect = [True, True, True, False]
    result_mock.get_next.side_effect = rows
    conn.execute.return_value = result_mock

    new_syntheses = synthesize_all(db_session, mock_synthesis_llm)
    assert new_syntheses == 1

    # Final state assertions
    assert db_session.query(Trend).filter_by(is_active=True).count() == 1
    assert db_session.query(Synthesis).filter_by(is_active=True).count() == 1
