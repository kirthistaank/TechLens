"""
Unit tests for the daily digest builder.
Uses in-memory DB — no Ollama calls, no email sending.
"""

import json
from datetime import date

import pytest

from techlens.digest.daily_digest import build_daily_digest
from techlens.storage.models import Article, ArticleStatus, Digest, Source


def _setup_source(db_session) -> Source:
    source = Source(id="src_dig", name="Test", feed_url="", home_url="https://example.com", source_type="rss")
    db_session.add(source)
    db_session.commit()
    return source


def _make_summarized_article(db_session, url: str, score: float, recommendation: str = "READ") -> Article:
    import hashlib
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=f"Article at {url}",
        publication="Test Source",
        source_id="src_dig",
        clean_content="Content.",
        status=ArticleStatus.summarized,
        score=score,
        recommendation=recommendation,
        summary_what="What happened in AI.",
        summary_why="Why this matters for architects.",
        summary_technical=json.dumps(["Insight A", "Insight B"]),
        summary_architecture="New pattern emerged.",
        summary_tradeoffs="Fast but costly.",
        estimated_reading_minutes=5,
        categories=json.dumps(["agentic_ai"]),
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_build_digest_includes_high_score_articles(db_session):
    """Articles above min_score (60) should appear in the digest."""
    _setup_source(db_session)
    _make_summarized_article(db_session, "https://example.com/a1", score=90.0)
    _make_summarized_article(db_session, "https://example.com/a2", score=75.0)

    digest = build_daily_digest(db_session)

    assert digest["date"] == date.today().isoformat()
    assert len(digest["items"]) == 2
    # Ordered by score descending
    assert digest["items"][0]["score"] == 90.0


def test_build_digest_excludes_low_score_articles(db_session):
    """Articles below min_score (60) should not appear in the digest."""
    _setup_source(db_session)
    _make_summarized_article(db_session, "https://example.com/high", score=85.0)
    _make_summarized_article(db_session, "https://example.com/low", score=30.0, recommendation="IGNORE")

    digest = build_daily_digest(db_session)

    assert len(digest["items"]) == 1
    assert digest["items"][0]["score"] == 85.0


def test_build_digest_caps_at_max_items(db_session):
    """Digest should never exceed max_daily_items (7) from profile.yaml."""
    _setup_source(db_session)
    for i in range(10):
        _make_summarized_article(db_session, f"https://example.com/a{i}", score=80.0 - i)

    digest = build_daily_digest(db_session)

    assert len(digest["items"]) <= 7


def test_build_digest_caches_on_second_call(db_session):
    """Calling build_daily_digest twice should return the cached Digest record."""
    _setup_source(db_session)
    _make_summarized_article(db_session, "https://example.com/cached", score=80.0)

    first = build_daily_digest(db_session)

    # Add another article after the first build
    _make_summarized_article(db_session, "https://example.com/new-after-cache", score=90.0)
    second = build_daily_digest(db_session)

    # Second call returns same cached result — new article not included
    assert first["generated_at"] == second["generated_at"]
    assert len(second["items"]) == len(first["items"])


def test_build_digest_excludes_duplicates(db_session):
    """Articles marked is_duplicate=True should not appear in the digest."""
    import hashlib
    _setup_source(db_session)
    _make_summarized_article(db_session, "https://example.com/original", score=85.0)

    url = "https://example.com/dup"
    dup = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Duplicate Article",
        publication="Test",
        source_id="src_dig",
        status=ArticleStatus.summarized,
        score=85.0,
        recommendation="READ",
        is_duplicate=True,
        categories="[]",
    )
    db_session.add(dup)
    db_session.commit()

    digest = build_daily_digest(db_session)
    assert len(digest["items"]) == 1
    assert digest["items"][0]["url"] == "https://example.com/original"
