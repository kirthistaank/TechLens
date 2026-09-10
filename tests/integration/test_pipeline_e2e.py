"""
End-to-end smoke test for the TechLens Phase 1 pipeline.
Uses fixture RSS XML as input, mocks trafilatura and Ollama so no network calls are made.
Verifies the full path: collect → extract → score → summarize → digest.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import feedparser
import pytest

from techlens.digest.daily_digest import build_daily_digest
from techlens.processing.extractor import process_pending
from techlens.ingestion.rss_collector import collect_source
from techlens.scoring.relevance_scorer import score_all
from techlens.storage.models import Article, ArticleStatus, Source
from techlens.summarization.summarizer import summarize_all

_FIXTURE_FEED = Path(__file__).parents[1] / "fixtures" / "sample_feed.xml"
_CLEAN_CONTENT = (
    "Enterprise RAG systems require careful attention to query encoding. "
    "Bi-encoders trained on domain data outperform general-purpose embeddings "
    "by up to 30% on recall@10 benchmarks. Architecture teams should treat "
    "the retriever as a first-class service rather than an afterthought."
)


@pytest.fixture()
def rss_source(db_session) -> Source:
    source = Source(
        id="e2e_feed",
        name="E2E Test Feed",
        feed_url="https://example.com/feed.xml",
        home_url="https://example.com",
        source_type="rss",
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_full_pipeline_produces_digest(db_session, rss_source, mock_scorer_llm, mock_summary_llm):
    """
    Smoke test: fixture RSS → collect → extract → score → summarize → digest.
    Asserts the digest is non-empty and all fields are populated.
    """
    parsed_feed = feedparser.parse(_FIXTURE_FEED.read_text())

    # Stage 1: Collect
    with patch("techlens.ingestion.rss_collector.feedparser.parse", return_value=parsed_feed):
        collected = collect_source(rss_source, db_session)

    assert collected == 2, f"Expected 2 recent articles, got {collected}"
    assert db_session.query(Article).count() == 2

    # Stage 2: Extract — use distinct content per article so dedup doesn't flag either one
    meta_mock = MagicMock()
    meta_mock.language = "en"
    _T = "techlens.processing.extractor.trafilatura"
    different_contents = [_CLEAN_CONTENT, _CLEAN_CONTENT + " (second article with unique content)"]
    with patch(f"{_T}.fetch_url", return_value="<html>...</html>"), \
         patch(f"{_T}.extract", side_effect=different_contents), \
         patch(f"{_T}.extract_metadata", return_value=meta_mock):
        extracted = process_pending(db_session)

    assert extracted == 2
    assert db_session.query(Article).filter_by(status=ArticleStatus.extracted).count() == 2

    # Stage 3: Score
    scored = score_all(db_session, mock_scorer_llm)
    assert scored == 2
    assert db_session.query(Article).filter_by(status=ArticleStatus.scored).count() == 2

    # Stage 4: Summarize
    summarized = summarize_all(db_session, mock_summary_llm)
    assert summarized == 2
    assert db_session.query(Article).filter_by(status=ArticleStatus.summarized).count() == 2

    # Stage 5: Build digest
    digest = build_daily_digest(db_session)

    # Assertions on digest output
    assert len(digest["items"]) > 0, "Digest must contain at least one item"
    assert digest["total_scored"] == 2

    item = digest["items"][0]
    assert item["title"] != ""
    assert item["score"] == 85.0
    assert item["recommendation"] == "READ"
    assert item["what_happened"] is not None
    assert item["why_it_matters"] is not None
    assert isinstance(item["technical_insights"], list)
    assert len(item["technical_insights"]) == 2
