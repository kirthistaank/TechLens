"""
Trend detector — Phase 3 autonomous agent.
Queries the Kuzu knowledge graph for concept clusters that appear across multiple sources
within rolling time windows, then calls the LLM to synthesise a trend card for each
qualifying cluster. Trend records (output) are persisted to SQLite; concept data lives in Kuzu.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from techlens.llm.base import LLMProvider
from techlens.storage.graph_store import get_article_ids_for_concept, get_concepts_in_window
from techlens.storage.models import Article, ArticleStatus, Trend, TrendArticle, utcnow

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You identify technology trends for a Principal AI Architect. "
    "Write concisely. Be specific about architecture implications. Respond with JSON only."
)

_USER_PROMPT_TEMPLATE = """The following technology/concept has appeared across multiple sources recently:
Concept: {concept_name}  (type: {concept_type})
Window: last {window_days} days
Article count: {article_count} articles
Source count: {source_count} distinct sources
Article titles:
{titles_list}

Write a trend card:
{{
  "name": "<short trend label, 4-7 words>",
  "summary": "<2-3 sentence description: what is happening, why it matters architecturally, what a Principal AI Architect should know or do>",
  "confidence": "<high|medium|low>"
}}
Use confidence=high if 4+ articles or 3+ sources, medium if 2-3 articles from 2 sources, low otherwise."""

_DEDUP_WINDOW_DAYS = 7    # suppress duplicate trend for the same concept within this period
_DEACTIVATE_AFTER_DAYS = 35


def _window_start(window_days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=window_days)


def _article_ids_in_window(session: Session, since: datetime) -> list[int]:
    """Return IDs of summarized articles retrieved within the window."""
    return [
        row[0]
        for row in session.query(Article.id)
        .filter(
            Article.retrieved_at >= since,
            Article.status == ArticleStatus.summarized,
        )
        .all()
    ]


def _trend_already_active(session: Session, concept_name: str, window_days: int) -> bool:
    """Return True if an active trend covering this concept was written in the last week."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_DEDUP_WINDOW_DAYS)
    existing = (
        session.query(Trend)
        .filter(
            Trend.is_active == True,  # noqa: E712
            Trend.window_days == window_days,
            Trend.detected_at >= cutoff,
        )
        .all()
    )
    for trend in existing:
        try:
            if concept_name in json.loads(trend.concepts):
                return True
        except (json.JSONDecodeError, TypeError):
            pass
    return False


def _write_trend_card(
    concept_name: str,
    concept_type: str,
    article_ids: list[int],
    window_days: int,
    llm: LLMProvider,
    session: Session,
) -> Trend | None:
    """Call LLM to write a trend card and persist it with its evidence articles to SQLite."""
    articles = session.query(Article).filter(Article.id.in_(article_ids)).all()
    source_ids = {a.source_id for a in articles}
    titles_list = "\n".join(f"- {a.title}" for a in articles)

    user_msg = _USER_PROMPT_TEMPLATE.format(
        concept_name=concept_name,
        concept_type=concept_type,
        window_days=window_days,
        article_count=len(articles),
        source_count=len(source_ids),
        titles_list=titles_list,
    )

    try:
        raw = llm.chat(_SYSTEM_PROMPT, user_msg, json_mode=True)
        data = json.loads(raw)
    except Exception as exc:
        logger.error("Trend card LLM call failed for concept '%s': %s", concept_name, exc)
        return None

    confidence = data.get("confidence", "low")
    if confidence not in ("high", "medium", "low"):
        confidence = "low"

    trend = Trend(
        name=data.get("name", concept_name),
        summary=data.get("summary", ""),
        confidence=confidence,
        window_days=window_days,
        article_count=len(articles),
        source_count=len(source_ids),
        concepts=json.dumps([concept_name]),
        detected_at=utcnow(),
        is_active=True,
    )
    session.add(trend)
    session.flush()

    for article in articles:
        session.add(TrendArticle(trend_id=trend.id, article_id=article.id))

    logger.info(
        "New trend: '%s' (concept=%s, window=%dd, articles=%d, sources=%d)",
        trend.name, concept_name, window_days, len(articles), len(source_ids),
    )
    return trend


def detect_trends(session: Session, llm: LLMProvider) -> int:
    """
    Autonomous trend detection agent. For each time window:
      1. Queries Kuzu for concept clusters present in that window's article set
      2. Filters to qualifying clusters (2+ sources, or 3+ articles single source)
      3. Skips concepts already covered by a recent active trend
      4. Calls LLM to write a trend card and persists it to SQLite

    Returns count of new trends detected.
    """
    # Deactivate trends older than the retention window
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=_DEACTIVATE_AFTER_DAYS)
    stale_count = (
        session.query(Trend)
        .filter(Trend.is_active == True, Trend.detected_at < stale_cutoff)  # noqa: E712
        .update({"is_active": False})
    )
    if stale_count:
        session.commit()
        logger.info("Deactivated %d stale trends", stale_count)

    new_trends = 0

    for window_days in [7, 30]:
        since = _window_start(window_days)
        window_article_ids = _article_ids_in_window(session, since)
        if not window_article_ids:
            continue

        # Ask Kuzu which concepts appear in this window's articles
        concept_clusters = get_concepts_in_window(window_article_ids)

        for cluster in concept_clusters:
            name = cluster["name"]
            ctype = cluster["concept_type"]
            article_count = cluster["article_count"]
            source_count = cluster["source_count"]

            qualifies = (source_count >= 2 and article_count >= 2) or (
                source_count == 1 and article_count >= 3
            )
            if not qualifies:
                continue

            if _trend_already_active(session, name, window_days):
                logger.debug("Skipping duplicate trend for '%s' (window=%dd)", name, window_days)
                continue

            # Get the specific article IDs for this concept within the window
            evidence_ids = get_article_ids_for_concept(name, window_article_ids)
            if not evidence_ids:
                continue

            trend = _write_trend_card(name, ctype, evidence_ids, window_days, llm, session)
            if trend:
                session.commit()
                new_trends += 1

    logger.info("Trend detection complete — %d new trends", new_trends)
    return new_trends
