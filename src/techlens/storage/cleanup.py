"""
Article purge utility — deletes articles older than article_purge_days from SQLite and ChromaDB.
Manually archived articles (is_archived=True) are always preserved regardless of age.
Saved (is_saved) and important (is_important) articles are also preserved.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from techlens.config import settings
from techlens.storage.models import Article, TrendArticle

logger = logging.getLogger(__name__)


def purge_old_articles(session: Session) -> int:
    """
    Delete articles retrieved more than article_purge_days ago, except those that are
    manually archived, saved, or marked important — those are kept forever.

    Also removes their embeddings from ChromaDB and cleans up TrendArticle join rows.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Number of articles deleted.
    """
    from techlens.storage.vector_store import delete_articles

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.article_purge_days)

    to_purge = (
        session.query(Article)
        .filter(
            Article.retrieved_at < cutoff,
            Article.is_archived == False,  # noqa: E712
            Article.is_saved == False,      # noqa: E712
            Article.is_important == False,  # noqa: E712
        )
        .all()
    )

    if not to_purge:
        logger.info("Purge: no articles older than %d days to remove", settings.article_purge_days)
        return 0

    ids = [a.id for a in to_purge]

    # Remove ChromaDB embeddings first
    delete_articles(ids)

    # Remove TrendArticle join rows to avoid orphaned FK references
    session.query(TrendArticle).filter(TrendArticle.article_id.in_(ids)).delete(synchronize_session=False)

    # Delete the articles
    session.query(Article).filter(Article.id.in_(ids)).delete(synchronize_session=False)
    session.commit()

    logger.info(
        "Purge: deleted %d articles older than %d days (archived/saved/important preserved)",
        len(ids),
        settings.article_purge_days,
    )
    return len(ids)
