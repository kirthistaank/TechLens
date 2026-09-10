"""
Unit tests for the relevance scoring stage.
Uses MockScorerLLM and MockFailingLLM from conftest — no Ollama calls.
"""

import json

import pytest

from techlens.scoring.relevance_scorer import score_article, score_all
from techlens.storage.models import Article, ArticleStatus, Source


def _make_extracted_article(db_session, url: str = "https://example.com/article-1") -> Article:
    import hashlib
    if not db_session.get(Source, "src"):
        db_session.add(Source(id="src", name="Test", feed_url="", home_url="https://example.com", source_type="rss"))
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Agentic AI in Enterprise Platforms",
        publication="Test Source",
        source_id="src",
        clean_content="Detailed content about agentic AI architectures and RAG patterns for enterprise.",
        status=ArticleStatus.extracted,
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_score_article_returns_valid_result(db_session, mock_scorer_llm):
    """score_article should parse LLM JSON and return a well-formed result dict."""
    article = _make_extracted_article(db_session)
    result = score_article(article, mock_scorer_llm)

    assert result["score"] == 85.0
    assert result["recommendation"] == "READ"
    assert isinstance(result["rationale"], str) and len(result["rationale"]) > 0
    assert "agentic_ai" in result["categories"]


def test_score_article_fallback_on_llm_error(db_session, mock_failing_llm):
    """When LLM raises, score_article should return the zero-score fallback."""
    article = _make_extracted_article(db_session)
    result = score_article(article, mock_failing_llm)

    assert result["score"] == 0.0
    assert result["recommendation"] == "IGNORE"
    assert result["rationale"] == "Scoring failed."


def test_score_all_updates_article_status(db_session, mock_scorer_llm):
    """score_all should set score, recommendation, and status=scored on each article."""
    _make_extracted_article(db_session, "https://example.com/a1")
    _make_extracted_article(db_session, "https://example.com/a2")

    count = score_all(db_session, mock_scorer_llm)

    assert count == 2
    articles = db_session.query(Article).all()
    for a in articles:
        assert a.status == ArticleStatus.scored
        assert a.score == 85.0
        assert a.recommendation == "READ"
        assert a.score_rationale is not None
        assert json.loads(a.categories) == ["agentic_ai", "rag", "enterprise_ai"]


def test_score_all_skips_duplicates(db_session, mock_scorer_llm):
    """Duplicate articles (is_duplicate=True) should not be scored."""
    import hashlib
    source = Source(id="src2", name="Test", feed_url="", home_url="https://example.com", source_type="rss")
    db_session.add(source)
    url = "https://example.com/dup"
    dup = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Duplicate Article",
        publication="Test",
        source_id="src2",
        clean_content="Some content.",
        status=ArticleStatus.extracted,
        is_duplicate=True,
    )
    db_session.add(dup)
    db_session.commit()

    count = score_all(db_session, mock_scorer_llm)
    assert count == 0
    db_session.refresh(dup)
    assert dup.score is None
