"""
Unit tests for the content extractor stage.
Mocks trafilatura so no real HTTP fetches are made.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from techlens.processing.extractor import extract_article, process_pending
from techlens.storage.models import Article, ArticleStatus, Source

_T = "techlens.processing.extractor.trafilatura"


def _make_source(db_session) -> Source:
    source = Source(
        id="test_src", name="Test", feed_url="", home_url="https://example.com", source_type="rss"
    )
    db_session.add(source)
    db_session.commit()
    return source


def _make_article(db_session, source: Source, url: str = "https://example.com/article-1") -> Article:
    article = Article(
        url=url,
        url_hash=hashlib.sha256(url.encode()).hexdigest(),
        title="Test Article",
        publication="Test Source",
        source_id=source.id,
        raw_content="<p>Short RSS summary.</p>",
    )
    db_session.add(article)
    db_session.commit()
    return article


def _meta(lang: str = "en") -> MagicMock:
    m = MagicMock()
    m.language = lang
    return m


def test_extract_article_uses_trafilatura_content(db_session):
    """extract_article should return trafilatura's cleaned text."""
    source = _make_source(db_session)
    article = _make_article(db_session, source)
    clean_text = "This is the cleaned article body from trafilatura."

    with patch(f"{_T}.fetch_url", return_value="<html>...</html>"), \
         patch(f"{_T}.extract", return_value=clean_text), \
         patch(f"{_T}.extract_metadata", return_value=_meta()):
        content, lang = extract_article(article)

    assert content == clean_text
    assert lang == "en"


def test_extract_article_falls_back_to_raw_content(db_session):
    """When trafilatura returns nothing, raw_content from RSS should be used."""
    source = _make_source(db_session)
    article = _make_article(db_session, source)

    with patch(f"{_T}.fetch_url", return_value=None):
        content, lang = extract_article(article)

    assert content == article.raw_content.strip()
    assert lang == "en"


def test_process_pending_marks_article_extracted(db_session):
    """process_pending should set status=extracted and populate clean_content."""
    source = _make_source(db_session)
    article = _make_article(db_session, source)
    clean_text = "Full article body text extracted by trafilatura."

    with patch(f"{_T}.fetch_url", return_value="<html>...</html>"), \
         patch(f"{_T}.extract", return_value=clean_text), \
         patch(f"{_T}.extract_metadata", return_value=_meta()):
        process_pending(db_session)

    db_session.refresh(article)
    assert article.status == ArticleStatus.extracted
    assert article.clean_content == clean_text


def test_process_pending_marks_failed_when_no_content(db_session):
    """When both trafilatura and raw_content are empty, status should be failed."""
    source = _make_source(db_session)
    article = Article(
        url="https://example.com/empty",
        url_hash=hashlib.sha256(b"https://example.com/empty").hexdigest(),
        title="Empty Article",
        publication="Test",
        source_id=source.id,
        raw_content=None,
    )
    db_session.add(article)
    db_session.commit()

    with patch(f"{_T}.fetch_url", return_value=None):
        process_pending(db_session)

    db_session.refresh(article)
    assert article.status == ArticleStatus.failed


def test_process_pending_detects_duplicate_content(db_session):
    """Two articles with identical content should have is_duplicate=True on the second."""
    source = _make_source(db_session)
    url1 = "https://example.com/article-a"
    url2 = "https://example.com/article-b"
    a1 = Article(url=url1, url_hash=hashlib.sha256(url1.encode()).hexdigest(),
                 title="Article A", publication="Test", source_id=source.id)
    a2 = Article(url=url2, url_hash=hashlib.sha256(url2.encode()).hexdigest(),
                 title="Article B", publication="Test", source_id=source.id)
    db_session.add_all([a1, a2])
    db_session.commit()

    same_content = "Identical article content that appears in both articles."
    with patch(f"{_T}.fetch_url", return_value="<html>...</html>"), \
         patch(f"{_T}.extract", return_value=same_content), \
         patch(f"{_T}.extract_metadata", return_value=_meta()):
        process_pending(db_session)

    db_session.refresh(a1)
    db_session.refresh(a2)
    duplicates = [a for a in [a1, a2] if a.is_duplicate]
    assert len(duplicates) == 1
