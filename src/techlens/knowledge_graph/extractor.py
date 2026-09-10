"""
Concept extractor — Phase 3 pipeline stage.
Calls the LLM to identify canonical technology/architecture concepts in each summarized
article's summary fields, then writes Concept nodes and MENTIONS edges into the Kuzu
graph database. Marks article.concepts_extracted = True in SQLite when done.
"""

import json
import logging

from sqlalchemy.orm import Session

from techlens.llm.base import LLMProvider
from techlens.storage.graph_store import (
    get_conn,
    link_article_concept,
    refresh_source_counts,
    upsert_article_node,
    upsert_concept,
)
from techlens.storage.models import Article, ArticleStatus, Recommendation

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You extract technology concepts and architecture patterns from article summaries "
    "for a knowledge graph. Be specific and consistent with naming. Use canonical names "
    '(e.g. "Model Context Protocol" not "MCP"). Respond with JSON only.'
)

_USER_PROMPT_TEMPLATE = """Article title: {title}
Summary:
What happened: {what_happened}
Why it matters: {why_it_matters}
Technical insights: {technical_insights}
Architecture implication: {architecture_implication}

Extract concepts mentioned in this article. Return:
{{
  "concepts": [
    {{"name": "<canonical name>", "type": "<technology|architecture_pattern|concept|company|product|research_area>", "role": "<primary|mentions>"}}
  ]
}}
Limit to 6 most relevant concepts. Only include technology/architecture concepts — no generic words."""

_VALID_TYPES = {"technology", "architecture_pattern", "concept", "company", "product", "research_area"}
_VALID_ROLES = {"primary", "mentions"}


def _normalise(name: str) -> str:
    """Strip whitespace and title-case a concept name for consistent graph storage."""
    return name.strip().title()


def extract_concepts(article: Article, llm: LLMProvider, session: Session) -> int:
    """
    Extract concepts from a single article's summary fields and write them to Kuzu.
    Marks article.concepts_extracted = True (caller commits to SQLite).

    Returns number of concept links written (0 on error or empty summary).
    """
    what = article.summary_what or ""
    why = article.summary_why or ""
    arch = article.summary_architecture or ""
    technical = article.get_technical_insights()

    if not (what or why or arch):
        article.concepts_extracted = True
        return 0

    user_msg = _USER_PROMPT_TEMPLATE.format(
        title=article.title,
        what_happened=what,
        why_it_matters=why,
        technical_insights="; ".join(technical) if technical else "N/A",
        architecture_implication=arch or "N/A",
    )

    try:
        raw = llm.chat(_SYSTEM_PROMPT, user_msg, json_mode=True)
        data = json.loads(raw)
    except Exception as exc:
        logger.error("Concept extraction failed for article %d: %s", article.id, exc)
        article.concepts_extracted = True
        return 0

    concepts_data: list[dict] = data.get("concepts", [])
    if not isinstance(concepts_data, list):
        article.concepts_extracted = True
        return 0

    conn = get_conn()
    upsert_article_node(conn, article.id, article.source_id)

    count = 0
    for item in concepts_data[:6]:
        name_raw = item.get("name", "").strip()
        ctype = item.get("type", "concept")
        role = item.get("role", "mentions")

        if not name_raw:
            continue
        if ctype not in _VALID_TYPES:
            ctype = "concept"
        if role not in _VALID_ROLES:
            role = "mentions"

        name = _normalise(name_raw)
        upsert_concept(conn, name, ctype)
        if link_article_concept(conn, article.id, name, role):
            count += 1

    article.concepts_extracted = True
    logger.debug("Extracted %d concepts from article %d (%s)", count, article.id, article.title[:60])
    return count


def extract_all(session: Session, llm: LLMProvider) -> int:
    """
    Run concept extraction on all summarized READ/SKIM articles not yet processed.
    Commits SQLite after each article. Refreshes Kuzu source counts once at the end.

    Returns total number of articles processed.
    """
    articles = (
        session.query(Article)
        .filter(
            Article.status == ArticleStatus.summarized,
            Article.concepts_extracted == False,  # noqa: E712
            Article.recommendation.in_([Recommendation.READ, Recommendation.SKIM]),
        )
        .all()
    )

    processed = 0
    for article in articles:
        extract_concepts(article, llm, session)
        session.commit()
        processed += 1

    if processed > 0:
        # Batch-update source counts in Kuzu now that all links are written
        refresh_source_counts(get_conn())

    logger.info("Concept extraction complete — %d articles processed", processed)
    return processed
