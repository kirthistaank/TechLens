"""
Article embedder — Stage 2b of the TechLens pipeline (Phase 2).
Embeds extracted articles with nomic-embed-text, stores vectors in ChromaDB,
and detects near-duplicate articles via cosine similarity.
Runs after process_pending() and before score_all().
"""

import logging

from techlens.config import settings
from techlens.embeddings.base import EmbeddingProvider
from techlens.storage.models import Article, ArticleStatus
from techlens.storage.vector_store import NEAR_DUPLICATE_DISTANCE, add_article, find_similar

logger = logging.getLogger(__name__)


def _article_metadata(article: Article) -> dict:
    """Build the ChromaDB metadata dict for an article."""
    return {
        "article_id": article.id,
        "title": article.title,
        "source": article.source_id,
        "score": article.score or 0.0,
        "recommendation": article.recommendation or "",
        "published_at": article.published_at.isoformat() if article.published_at else "",
    }


def embed_articles(session, embedder: EmbeddingProvider) -> int:
    """
    Embed all extracted articles that are not yet in the vector store.

    For each article:
    1. Generate an embedding from clean_content.
    2. Check ChromaDB for near-duplicates (cosine distance < threshold).
    3. If a near-duplicate exists and is older, mark the current article as a duplicate.
    4. Store the embedding in ChromaDB regardless (for future search).

    Args:
        session:  Active SQLAlchemy session.
        embedder: EmbeddingProvider to use (nomic-embed-text by default).

    Returns:
        Number of articles embedded.
    """
    articles = (
        session.query(Article)
        .filter(
            Article.status == ArticleStatus.extracted,
            Article.is_duplicate == False,  # noqa: E712
        )
        .all()
    )

    embedded = 0
    near_dups = 0

    for article in articles:
        content = article.clean_content or article.raw_content or ""
        if not content.strip():
            continue

        try:
            embedding = embedder.embed(content)
        except Exception as exc:
            logger.warning("Embedding failed for article %d: %s", article.id, exc)
            continue

        # Check for near-duplicates before storing this embedding
        similar = find_similar(
            embedding,
            n_results=1,
            exclude_id=article.id,
            max_distance=settings.semantic_dedup_threshold,
        )
        if similar:
            best = similar[0]
            logger.info(
                "Near-duplicate: article %d ≈ article %d (distance=%.4f) — '%s'",
                article.id, best["id"], best["distance"], article.title[:60],
            )
            article.is_duplicate = True
            article.canonical_article_id = best["id"]
            near_dups += 1

        # Always store embedding so this article is searchable and can be a canonical for future dupes
        add_article(article.id, content, _article_metadata(article), embedding)
        embedded += 1

    session.commit()
    logger.info("Embedded %d articles (%d near-duplicates detected)", embedded, near_dups)
    return embedded


def update_embedding_metadata(article: Article, embedder: EmbeddingProvider) -> None:
    """
    Refresh the ChromaDB metadata for an article after scoring/summarization.
    Keeps score and recommendation in sync with the vector store for filtered search.

    Args:
        article:  The article whose metadata should be refreshed.
        embedder: EmbeddingProvider used to re-embed the content.
    """
    content = article.clean_content or article.raw_content or ""
    if content.strip():
        try:
            embedding = embedder.embed(content)
            add_article(article.id, content, _article_metadata(article), embedding)
        except Exception as exc:
            logger.warning("Metadata update failed for article %d: %s", article.id, exc)
