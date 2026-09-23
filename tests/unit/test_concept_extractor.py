"""
Unit tests for the Phase 3 concept extractor.
Patches all Kuzu graph_store calls — no real Kuzu DB required.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from techlens.knowledge_graph.extractor import extract_all, extract_concepts
from techlens.storage.models import Article, ArticleStatus, Recommendation, Source


def _make_source(db_session, sid: str = "src") -> Source:
    if not db_session.get(Source, sid):
        src = Source(id=sid, name="Test", feed_url="", home_url="https://example.com", source_type="rss")
        db_session.add(src)
        db_session.commit()
    return db_session.get(Source, sid)


def _make_summarized_article(
    db_session,
    url: str = "https://example.com/a1",
    source_id: str = "src",
    recommendation: str = "READ",
) -> Article:
    _make_source(db_session, source_id)
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Agent Memory Patterns in Production Systems",
        publication="Test",
        source_id=source_id,
        clean_content="Content about agent memory.",
        status=ArticleStatus.summarized,
        recommendation=recommendation,
        summary_what="A new approach to agent memory was published.",
        summary_why="Directly relevant to enterprise AI platform design.",
        summary_architecture="Separate episodic from semantic memory stores.",
        summary_technical='["Bi-encoder outperforms cross-encoder at scale"]',
        concepts_extracted=False,
    )
    db_session.add(article)
    db_session.commit()
    return article


@patch("techlens.knowledge_graph.extractor.refresh_source_counts")
@patch("techlens.knowledge_graph.extractor.link_article_concept", return_value=True)
@patch("techlens.knowledge_graph.extractor.upsert_concept")
@patch("techlens.knowledge_graph.extractor.upsert_article_node")
@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_concepts_writes_to_graph(
    mock_get_conn, mock_upsert_node, mock_upsert_concept, mock_link, mock_refresh,
    db_session, mock_extractor_llm,
):
    """extract_concepts should call graph_store writes and return the number of links created."""
    mock_get_conn.return_value = MagicMock()
    article = _make_summarized_article(db_session)

    count = extract_concepts(article, mock_extractor_llm, db_session)

    assert count == 3
    assert article.concepts_extracted is True
    mock_upsert_node.assert_called_once()
    assert mock_upsert_concept.call_count == 3
    assert mock_link.call_count == 3


@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_concepts_empty_summary_skips_llm(mock_get_conn, db_session, mock_extractor_llm):
    """Articles with no summary fields should be marked done without calling the LLM."""
    _make_source(db_session)
    url = "https://example.com/empty"
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Empty",
        publication="Test",
        source_id="src",
        status=ArticleStatus.summarized,
        recommendation="READ",
        concepts_extracted=False,
    )
    db_session.add(article)
    db_session.commit()

    count = extract_concepts(article, mock_extractor_llm, db_session)

    assert count == 0
    assert article.concepts_extracted is True
    mock_get_conn.assert_not_called()


@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_concepts_llm_failure_marks_done(mock_get_conn, db_session, mock_failing_llm):
    """When the LLM raises, concepts_extracted should still be set to True (skip on next run)."""
    article = _make_summarized_article(db_session, url="https://example.com/fail")

    count = extract_concepts(article, mock_failing_llm, db_session)

    assert count == 0
    assert article.concepts_extracted is True


@patch("techlens.knowledge_graph.extractor.refresh_source_counts")
@patch("techlens.knowledge_graph.extractor.link_article_concept", return_value=True)
@patch("techlens.knowledge_graph.extractor.upsert_concept")
@patch("techlens.knowledge_graph.extractor.upsert_article_node")
@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_all_processes_unextracted_articles(
    mock_get_conn, mock_upsert_node, mock_upsert_concept, mock_link, mock_refresh,
    db_session, mock_extractor_llm,
):
    """extract_all should process all READ/SKIM summarized articles not yet extracted."""
    mock_get_conn.return_value = MagicMock()
    _make_summarized_article(db_session, url="https://example.com/b1", recommendation="READ")
    _make_summarized_article(db_session, url="https://example.com/b2", recommendation="SKIM")

    processed = extract_all(db_session, mock_extractor_llm)

    assert processed == 2
    mock_refresh.assert_called_once()


@patch("techlens.knowledge_graph.extractor.refresh_source_counts")
@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_all_skips_already_extracted(mock_get_conn, mock_refresh, db_session, mock_extractor_llm):
    """Articles with concepts_extracted=True must be skipped by extract_all."""
    _make_source(db_session)
    url = "https://example.com/done"
    done = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Already Done",
        publication="Test",
        source_id="src",
        status=ArticleStatus.summarized,
        recommendation="READ",
        summary_what="Done.",
        concepts_extracted=True,
    )
    db_session.add(done)
    db_session.commit()

    processed = extract_all(db_session, mock_extractor_llm)

    assert processed == 0
    mock_refresh.assert_not_called()


@patch("techlens.knowledge_graph.extractor.refresh_source_counts")
@patch("techlens.knowledge_graph.extractor.get_conn")
def test_extract_all_skips_ignore_recommendation(mock_get_conn, mock_refresh, db_session, mock_extractor_llm):
    """IGNORE articles should not be processed even if summarized and not yet extracted."""
    _make_summarized_article(db_session, url="https://example.com/ignore", recommendation="IGNORE")

    processed = extract_all(db_session, mock_extractor_llm)

    assert processed == 0
