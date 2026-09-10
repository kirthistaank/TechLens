"""
Summarizer — Stage 4 of the TechLens pipeline.
Calls the LLM to produce a structured summary for each READ/SKIM article:
what happened, why it matters, technical insights, architecture implication, and tradeoffs.
IGNORE articles are skipped to save inference time.
"""

import json
import logging
import time

from techlens.config import settings
from techlens.llm.base import LLMProvider
from techlens.storage.models import Article, ArticleStatus, Recommendation

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a technical briefing assistant for a Principal AI Architect.
Produce a concise, structured summary. Be specific and technical. Do NOT pad with filler.
Every sentence must deliver information. Avoid restating the title.
Respond with JSON only."""

_USER_PROMPT_TEMPLATE = """Summarize this article for a Principal AI Architect:

Title: {title}
Source: {source}
Content:
{content}

Return this JSON:
{{
  "what_happened": "<max 2 sentences — the factual development>",
  "why_it_matters": "<max 2 sentences — career/architecture relevance>",
  "technical_insights": ["<specific bullet 1>", "<specific bullet 2>", "<optional bullet 3>"],
  "architecture_implication": "<what changes architecturally, or what pattern this represents>",
  "tradeoffs": "<concrete benefits and costs>",
  "estimated_reading_minutes": <integer>
}}"""


def summarize_article(article: Article, llm: LLMProvider) -> dict | None:
    content = article.clean_content or article.raw_content or ""
    if not content.strip():
        return None

    user_msg = _USER_PROMPT_TEMPLATE.format(
        title=article.title,
        source=article.publication,
        content=content[:6000],
    )

    try:
        raw = llm.chat(_SYSTEM_PROMPT, user_msg, json_mode=True)
        return json.loads(raw)
    except Exception as exc:
        logger.error("Summarization failed for article %d: %s", article.id, exc)
        return None


def summarize_all(session, llm: LLMProvider) -> int:
    q = session.query(Article).filter(Article.status == ArticleStatus.scored)
    if settings.llm_batch_size > 0:
        q = q.limit(settings.llm_batch_size)
    articles = q.all()

    summarized = 0
    for article in articles:
        if article.recommendation == Recommendation.IGNORE:
            article.status = ArticleStatus.ignored
            continue

        result = summarize_article(article, llm)
        if result:
            article.summary_what = result.get("what_happened", "")
            article.summary_why = result.get("why_it_matters", "")
            article.summary_technical = json.dumps(result.get("technical_insights", []))
            article.summary_architecture = result.get("architecture_implication", "")
            article.summary_tradeoffs = result.get("tradeoffs", "")
            article.estimated_reading_minutes = result.get("estimated_reading_minutes")
        article.status = ArticleStatus.summarized
        summarized += 1
        if settings.llm_throttle_seconds > 0 and summarized < len(articles):
            time.sleep(settings.llm_throttle_seconds)

    session.commit()
    logger.info("Summarized %d articles", summarized)
    return summarized
