"""
Cross-source synthesis — Phase 3 pipeline stage.
When 3+ articles from 2+ different sources cover the same concept, calls the LLM to generate
a single synthesised card that eliminates redundancy and surfaces unique per-source perspectives.
Synthesis records are persisted to SQLite; stale records (>14 days) are deactivated each run.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from techlens.llm.base import LLMProvider
from techlens.storage.models import Article, Synthesis, utcnow

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You synthesise multiple articles about the same technology topic for a Principal AI Architect. "  # noqa: E501
    "Eliminate redundancy. Surface what is unique in each source's perspective. "
    "Be concise and technical. Respond with JSON only."
)

_USER_PROMPT_TEMPLATE = """\
The following {n} articles from {source_count} sources all cover the same topic: "{concept_name}"

{articles_block}

Synthesise into one card:
{{
  "topic": "<4-6 word label for this event/development>",
  "summary": "<2-3 sentences: what happened, synthesising facts across all sources, no repetition>",
  "unique_perspectives": ["<what source A adds that others don't>", "<what source B adds>"],
  "key_insight": "<one sentence: the single most important architecture takeaway>"
}}"""

_DEACTIVATE_AFTER_DAYS = 14


def _get_existing_article_ids(session: Session) -> set[int]:
    """
    Return all article IDs that are already covered by an active Synthesis record.
    Used to skip clusters that are already synthesised.
    """
    active = session.query(Synthesis).filter(Synthesis.is_active == True).all()  # noqa: E712
    covered: set[int] = set()
    for s in active:
        try:
            covered.update(json.loads(s.article_ids))
        except (ValueError, TypeError):
            pass
    return covered


def _overlap_fraction(new_ids: list[int], covered_ids: set[int]) -> float:
    """Return the fraction of new_ids that are already covered by existing syntheses."""
    if not new_ids:
        return 0.0
    overlap = sum(1 for aid in new_ids if aid in covered_ids)
    return overlap / len(new_ids)


def _build_articles_block(articles: list[Article]) -> str:
    """
    Format a list of Article ORM objects into the multi-source block used in the LLM prompt.
    Each article contributes its source, title, and summary fields.
    """
    parts = []
    for a in articles:
        block = (
            f"[Source: {a.source_id}]\n"
            f"Title: {a.title}\n"
            f"What happened: {a.summary_what or 'N/A'}\n"
            f"Why it matters: {a.summary_why or 'N/A'}\n"
            f"Architecture implication: {a.summary_architecture or 'N/A'}"
        )
        parts.append(block)
    return "\n\n".join(parts)


def synthesize_cluster(
    concept_name: str,
    articles: list[Article],
    llm: LLMProvider,
    session: Session,
) -> Synthesis | None:
    """
    Call the LLM to synthesise a cluster of articles about the same concept and
    persist the resulting Synthesis record to SQLite.

    Args:
        concept_name: The Kuzu concept name that unites this cluster.
        articles:     Article ORM objects to synthesise (already fetched from SQLite).
        llm:          LLMProvider instance for the synthesis call.
        session:      Active SQLAlchemy session for persistence.

    Returns:
        The new Synthesis ORM object, or None if the LLM call fails.
    """
    source_ids = list({a.source_id for a in articles})
    articles_block = _build_articles_block(articles)

    user_msg = _USER_PROMPT_TEMPLATE.format(
        n=len(articles),
        source_count=len(source_ids),
        concept_name=concept_name,
        articles_block=articles_block,
    )

    try:
        raw = llm.chat(_SYSTEM_PROMPT, user_msg, json_mode=True)
        data = json.loads(raw)
    except Exception as exc:
        logger.error("Synthesis LLM call failed for concept '%s': %s", concept_name, exc)
        return None

    unique_perspectives = data.get("unique_perspectives", [])
    if not isinstance(unique_perspectives, list):
        unique_perspectives = []

    synthesis = Synthesis(
        topic=data.get("topic", concept_name),
        summary=data.get("summary", ""),
        unique_perspectives=json.dumps(unique_perspectives),
        key_insight=data.get("key_insight", ""),
        source_count=len(source_ids),
        article_count=len(articles),
        concepts=json.dumps([concept_name]),
        article_ids=json.dumps([a.id for a in articles]),
        generated_at=utcnow(),
        is_active=True,
    )
    session.add(synthesis)
    session.flush()

    logger.info(
        "New synthesis: '%s' (concept=%s, articles=%d, sources=%d)",
        synthesis.topic, concept_name, len(articles), len(source_ids),
    )
    return synthesis


def synthesize_all(session: Session, llm: LLMProvider) -> int:
    """
    Run the full cross-source synthesis algorithm.

    Algorithm:
      1. Query Kuzu for concept -> article mappings (concept_name, article_id, source_id).
      2. Group by concept: filter to concepts with distinct source_count >= 2, article_count >= 3.
      3. Dedup: skip if >50% of the cluster's article IDs are already in an active Synthesis.
      4. Fetch Article ORM objects from SQLite, call LLM, persist Synthesis record.
      5. Deactivate Synthesis records older than 14 days.

    Args:
        session: Active SQLAlchemy session.
        llm:     LLMProvider for synthesis calls.

    Returns:
        Count of new Synthesis records created.
    """
    # Deactivate stale syntheses
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=_DEACTIVATE_AFTER_DAYS)
    stale_count = (
        session.query(Synthesis)
        .filter(Synthesis.is_active == True, Synthesis.generated_at < stale_cutoff)  # noqa: E712
        .update({"is_active": False})
    )
    if stale_count:
        session.commit()
        logger.info("Deactivated %d stale syntheses", stale_count)

    # Query Kuzu for all concept -> article mappings
    from techlens.storage.graph_store import get_conn
    conn = get_conn()
    result = conn.execute(
        "MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept) "
        "RETURN c.name, a.article_id, a.source_id"
    )

    # Group by concept: {concept_name: {article_ids: set, source_ids: set}}
    clusters: dict[str, dict[str, set]] = {}
    while result.has_next():
        row = result.get_next()
        cname, article_id, source_id = row[0], row[1], row[2]
        if cname not in clusters:
            clusters[cname] = {"article_ids": set(), "source_ids": set()}
        clusters[cname]["article_ids"].add(article_id)
        clusters[cname]["source_ids"].add(source_id)

    # Filter qualifying clusters
    qualifying = {
        name: data
        for name, data in clusters.items()
        if len(data["source_ids"]) >= 2 and len(data["article_ids"]) >= 3
    }

    if not qualifying:
        logger.info("Synthesis: no qualifying clusters found")
        return 0

    # Load already-covered article IDs to skip duplicates
    covered_ids = _get_existing_article_ids(session)

    new_syntheses = 0
    for concept_name, cluster_data in qualifying.items():
        article_ids = list(cluster_data["article_ids"])

        # Skip if >50% overlap with existing active syntheses
        if _overlap_fraction(article_ids, covered_ids) > 0.5:
            logger.debug("Skipping synthesis for '%s' — already covered", concept_name)
            continue

        # Fetch Article ORM objects from SQLite
        articles = session.query(Article).filter(Article.id.in_(article_ids)).all()
        if not articles:
            continue

        synthesis = synthesize_cluster(concept_name, articles, llm, session)
        if synthesis:
            session.commit()
            # Add newly covered IDs to the in-memory set to avoid re-covering within this run
            covered_ids.update(article_ids)
            new_syntheses += 1

    logger.info("Synthesis complete — %d new synthesis cards created", new_syntheses)
    return new_syntheses
