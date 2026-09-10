"""
Relevance scorer — Stage 3 of the TechLens pipeline.
Sends each extracted article to the LLM with a rubric prompt and receives a 0–100 score,
READ/SKIM/IGNORE recommendation, rationale, and category tags.
Scoring is personalised to a Principal AI Architect career profile loaded from profile.yaml.
"""

import json
import logging
import time
from pathlib import Path

import yaml

from techlens.config import settings
from techlens.llm.base import LLMProvider
from techlens.storage.models import Article, ArticleStatus, Recommendation

logger = logging.getLogger(__name__)

_PROFILE_PATH = Path(__file__).parents[3] / "config" / "profile.yaml"

_SYSTEM_PROMPT = """You are a relevance scoring system for a Principal AI Architect.
Your job is to assess whether a tech/AI article is worth reading given the user's career goals.

The user is a Senior/Principal-level AI Architect pursuing a Principal AI Architect / Enterprise AI Platform role.
They want to improve: technical depth, architecture knowledge, emerging AI understanding, system-design capability, enterprise AI knowledge, interview readiness.

Score strictly. Penalize heavily:
- Consumer AI applications
- Generic "AI will change everything" opinion pieces
- Marketing-heavy announcements with no technical substance
- Repetitive coverage of already-widely-reported news
- AI funding/business news without architecture relevance

Respond with JSON only. No explanation outside the JSON."""

_USER_PROMPT_TEMPLATE = """Article to score:

Title: {title}
Source: {source}
Content (truncated to first 4000 chars):
{content}

Tier 1 topics (highest priority): {tier1}
Tier 2 topics: {tier2}

Return this JSON:
{{
  "score": <integer 0-100>,
  "recommendation": "<READ|SKIM|IGNORE>",
  "rationale": "<1-2 sentences explaining the score>",
  "categories": ["<matched category>"]
}}"""


def _load_tier1() -> list[str]:
    with open(_PROFILE_PATH) as f:
        profile = yaml.safe_load(f)
    return profile["relevance_tiers"]["tier1"]["topics"]


def _load_tier2() -> list[str]:
    with open(_PROFILE_PATH) as f:
        profile = yaml.safe_load(f)
    return profile["relevance_tiers"]["tier2"]["topics"]


def score_article(article: Article, llm: LLMProvider, system_prompt: str = _SYSTEM_PROMPT) -> dict:
    """
    Score a single article using the LLM.

    Args:
        article:       Article ORM object with extracted content.
        llm:           LLMProvider instance.
        system_prompt: System prompt to use (caller may inject personalization hints).

    Returns:
        Dict with keys: score, recommendation, rationale, categories.
    """
    content = article.clean_content or article.raw_content or ""
    user_msg = _USER_PROMPT_TEMPLATE.format(
        title=article.title,
        source=article.publication,
        content=content[:4000],
        tier1=", ".join(_load_tier1()),
        tier2=", ".join(_load_tier2()),
    )

    try:
        raw = llm.chat(system_prompt, user_msg, json_mode=True)
        result = json.loads(raw)
        return {
            "score": float(result.get("score", 0)),
            "recommendation": result.get("recommendation", "IGNORE"),
            "rationale": result.get("rationale", ""),
            "categories": result.get("categories", []),
        }
    except Exception as exc:
        logger.error("Scoring failed for article %d: %s", article.id, exc)
        return {"score": 0.0, "recommendation": "IGNORE", "rationale": "Scoring failed.", "categories": []}


def score_all(session, llm: LLMProvider) -> int:
    """
    Score all extracted articles. Builds a personalized system prompt by appending
    any accumulated feedback weights from config/user_weights.yaml, so each pipeline
    run benefits from the user's prior reading behaviour.
    """
    from techlens.scoring.feedback_weights import build_personalization_hint

    personalization = build_personalization_hint()
    system_prompt = _SYSTEM_PROMPT + personalization
    if personalization:
        logger.info("Adaptive scoring enabled — personalization hint injected into prompt")

    q = (
        session.query(Article)
        .filter(Article.status == ArticleStatus.extracted, Article.is_duplicate == False)  # noqa: E712
    )
    if settings.llm_batch_size > 0:
        q = q.limit(settings.llm_batch_size)
    articles = q.all()

    scored = 0
    for article in articles:
        result = score_article(article, llm, system_prompt=system_prompt)
        article.score = result["score"]
        article.recommendation = result["recommendation"]
        article.score_rationale = result["rationale"]
        article.categories = json.dumps(result["categories"])
        article.status = ArticleStatus.scored
        scored += 1
        if settings.llm_throttle_seconds > 0 and scored < len(articles):
            time.sleep(settings.llm_throttle_seconds)

    session.commit()
    logger.info("Scored %d articles", scored)
    return scored
