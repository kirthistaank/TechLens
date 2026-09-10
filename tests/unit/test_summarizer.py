"""
Unit tests for the summarization stage.
Uses MockSummaryLLM and MockFailingLLM from conftest — no Ollama calls.
"""

import json

import pytest

from techlens.storage.models import Article, ArticleStatus, Source
from techlens.summarization.summarizer import summarize_article, summarize_all


def _make_scored_article(db_session, url: str, recommendation: str = "READ") -> Article:
    import hashlib
    source = db_session.get(Source, "src_sum")
    if not source:
        source = Source(id="src_sum", name="Test", feed_url="", home_url="https://example.com", source_type="rss")
        db_session.add(source)
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Enterprise RAG Architecture Deep Dive",
        publication="Test Source",
        source_id="src_sum",
        clean_content="Detailed technical content about retrieval-augmented generation at scale.",
        status=ArticleStatus.scored,
        score=85.0,
        recommendation=recommendation,
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_summarize_article_populates_all_fields(db_session, mock_summary_llm):
    """summarize_article should return all expected summary fields from LLM."""
    article = _make_scored_article(db_session, "https://example.com/rag-deep-dive")
    result = summarize_article(article, mock_summary_llm)

    assert result is not None
    assert "RAG" in result["what_happened"] or "enterprise" in result["what_happened"].lower() or "approach" in result["what_happened"]
    assert isinstance(result["technical_insights"], list)
    assert len(result["technical_insights"]) == 2
    assert result["estimated_reading_minutes"] == 6


def test_summarize_article_returns_none_on_llm_error(db_session, mock_failing_llm):
    """When LLM fails, summarize_article should return None (caller handles it)."""
    article = _make_scored_article(db_session, "https://example.com/fail-article")
    result = summarize_article(article, mock_failing_llm)
    assert result is None


def test_summarize_all_processes_read_and_skim(db_session, mock_summary_llm):
    """summarize_all should process READ and SKIM articles and set status=summarized."""
    read_a = _make_scored_article(db_session, "https://example.com/read-1", "READ")
    skim_a = _make_scored_article(db_session, "https://example.com/skim-1", "SKIM")

    count = summarize_all(db_session, mock_summary_llm)

    assert count == 2
    for a in [read_a, skim_a]:
        db_session.refresh(a)
        assert a.status == ArticleStatus.summarized
        assert a.summary_what is not None
        assert a.summary_why is not None
        assert json.loads(a.summary_technical) == [
            "Bi-encoder outperforms cross-encoder at scale",
            "HyDE adds latency but improves recall by 20%",
        ]
        assert a.estimated_reading_minutes == 6


def test_summarize_all_skips_ignore_articles(db_session, mock_summary_llm):
    """IGNORE-scored articles should not be summarized."""
    ignore_a = _make_scored_article(db_session, "https://example.com/ignore-1", "IGNORE")

    count = summarize_all(db_session, mock_summary_llm)

    assert count == 0
    db_session.refresh(ignore_a)
    assert ignore_a.summary_what is None
    assert ignore_a.status == ArticleStatus.scored  # unchanged
