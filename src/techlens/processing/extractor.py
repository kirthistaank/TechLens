"""
Content extractor — Stage 2 of the TechLens pipeline.
Uses trafilatura to fetch and clean article HTML (strips nav, ads, boilerplate).
Also detects exact content duplicates via SHA-256 hash of the cleaned text.
"""

import hashlib
import logging

import trafilatura

from techlens.storage.db import get_session
from techlens.storage.models import Article, ArticleStatus

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def extract_article(article: Article) -> tuple[str | None, str | None]:
    """Return (clean_content, language) for an article URL."""
    try:
        downloaded = trafilatura.fetch_url(article.url)
        if not downloaded:
            # Fall back to raw_content from RSS summary
            if article.raw_content:
                return article.raw_content.strip(), "en"
            return None, None

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
        if not text:
            return article.raw_content, "en"

        meta = trafilatura.extract_metadata(downloaded)
        language = meta.language if meta and meta.language else "en"
        return text.strip(), language

    except Exception as exc:
        logger.warning("Extraction failed for %s: %s", article.url, exc)
        return article.raw_content, "en"


def process_pending(session) -> int:
    """Extract content for all pending articles."""
    articles = session.query(Article).filter_by(status=ArticleStatus.pending).all()
    processed = 0

    for article in articles:
        clean, lang = extract_article(article)

        if clean:
            chash = _content_hash(clean)
            # Mark as duplicate if identical content already exists
            duplicate = (
                session.query(Article)
                .filter(
                    Article.content_hash == chash,
                    Article.id != article.id,
                )
                .first()
            )
            if duplicate:
                article.is_duplicate = True
                article.canonical_article_id = duplicate.id

            article.clean_content = clean[:50000]  # hard cap
            article.content_hash = chash
            article.language = lang
            article.status = ArticleStatus.extracted
        else:
            article.status = ArticleStatus.failed

        processed += 1

    session.commit()
    logger.info("Extracted %d articles", processed)
    return processed
