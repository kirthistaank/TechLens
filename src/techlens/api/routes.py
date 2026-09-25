"""
FastAPI route definitions for TechLens.
Covers digest retrieval, article listing/filtering, source management,
manual pipeline triggering, pipeline status checks, semantic search (Phase 2),
and Phase 3 knowledge-graph endpoints: /api/trends, /api/concepts,
/api/synthesis (cross-source synthesis), and /api/knowledge/map.
Includes rate limiting via slowapi for DDoS protection.
"""

import json
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from techlens.api.limiter import limiter
from techlens.api.schemas import (
    ArticleOut,
    ConfigOut,
    ConceptKnowledgeItem,
    ConceptOut,
    DigestOut,
    JoinDemoRequest,
    JoinDemoResponse,
    KnowledgeMapOut,
    PipelineStatus,
    RateRequest,
    SourceCreate,
    SourceOut,
    SynthesisOut,
    TrendOut,
)
from techlens.storage.db import get_db
from techlens.storage.models import (
    Article,
    ArticleStatus,
    Digest,
    Source,
    Synthesis,
    Trend,
    UserJoined,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# --- Digest ---

@router.get("/digest/daily", response_model=DigestOut)
@limiter.limit("200/day;30/hour")
def get_daily_digest(request: Request, session: Session = Depends(get_db)):
    """
    Return today's digest. If no digest record exists yet but summarized articles
    are available, build it on-demand so the UI never shows a hard 404.
    Returns an empty digest structure when no articles have been processed yet.
    """
    from techlens.digest.daily_digest import build_daily_digest

    today = date.today().isoformat()
    record = session.query(Digest).filter_by(date=today, digest_type="daily").first()
    if record:
        cached = json.loads(record.content)
        # If cached digest is empty but summarized articles now exist, rebuild it
        summarized_count = (
            session.query(Article)
            .filter_by(status=ArticleStatus.summarized)
            .count()
        )
        if cached["items"] or summarized_count == 0:
            # Filter out any items the user has since archived
            archived_ids = {
                a.id for a in session.query(Article).filter_by(is_archived=True).all()
            }
            cached["items"] = [i for i in cached["items"] if i["id"] not in archived_ids]
            return cached
        # Stale empty cache — delete and fall through to rebuild
        session.delete(record)
        session.commit()

    # Build on-demand if any summarized articles exist
    summarized_count = (
        session.query(Article)
        .filter_by(status=ArticleStatus.summarized)
        .count()
    )
    if summarized_count > 0:
        return build_daily_digest(session)

    # Nothing processed yet — return empty shell so the UI shows a friendly state
    from datetime import datetime, timezone
    return {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_collected": session.query(Article).count(),
        "total_scored": session.query(Article).filter(Article.score.isnot(None)).count(),
        "items": [],
    }


# --- Demo Access ---

def get_ngrok_url() -> str:
    """Get current ngrok URL from file."""
    ngrok_url_file = Path("/home/opc/techlens/current_ngrok_url.txt")
    if ngrok_url_file.exists():
        return ngrok_url_file.read_text().strip()
    return "http://localhost:8000"


@router.get("/config", response_model=ConfigOut)
def get_config():
    """Public configuration endpoint for frontend discovery of backend URL."""
    return ConfigOut(ngrok_url=get_ngrok_url())


@router.post("/join-demo", response_model=JoinDemoResponse)
def join_demo(request: Request, body: JoinDemoRequest, session: Session = Depends(get_db)):
    """
    User signup endpoint. Generates temporary access token for demo.
    """
    # Check if user already exists with valid token
    existing = session.query(UserJoined).filter_by(email=body.email).first()
    if existing and existing.is_token_valid():
        return JoinDemoResponse(
            access_token=existing.access_token,
            ngrok_url=get_ngrok_url(),
            expires_in_hours=24,
            message="Welcome back! Your token is still valid."
        )

    # Generate new token
    access_token = secrets.token_urlsafe(32)
    token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Store in database
    user = UserJoined(
        name=body.name,
        email=body.email,
        access_token=access_token,
        token_expires_at=token_expires_at
    )
    session.add(user)
    session.commit()

    logger.info(f"User joined demo: {body.email}")

    return JoinDemoResponse(
        access_token=access_token,
        ngrok_url=get_ngrok_url(),
        expires_in_hours=24,
        message=f"Welcome {body.name}! Your demo access is ready."
    )


@router.get("/validate-token")
def validate_token(token: str, session: Session = Depends(get_db)):
    """Check if access token is valid."""
    user = session.query(UserJoined).filter_by(access_token=token).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not user.is_token_valid():
        raise HTTPException(status_code=401, detail="Token expired")

    # Update last accessed time
    user.accessed_at = datetime.now(timezone.utc)
    session.commit()

    return {
        "valid": True,
        "name": user.name,
        "email": user.email,
        "expires_at": user.token_expires_at
    }


# --- Articles ---

@router.get("/articles", response_model=list[ArticleOut])
def list_articles(
    recommendation: str | None = None,
    archived: bool = False,
    saved: bool = False,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_db),
):
    q = session.query(Article).filter(
        Article.score.isnot(None),
        Article.is_archived == archived,
    )
    if saved:
        q = q.filter(Article.is_saved == True)  # noqa: E712
    if recommendation:
        q = q.filter(Article.recommendation == recommendation.upper())
    articles = q.order_by(Article.score.desc()).offset(offset).limit(limit).all()
    return [_article_to_schema(a) for a in articles]


@router.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, session: Session = Depends(get_db)):
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return _article_to_schema(article)


@router.patch("/articles/{article_id}/archive", response_model=ArticleOut)
def toggle_archive(article_id: int, session: Session = Depends(get_db)):
    """Toggle the archived state of an article."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    article.is_archived = not article.is_archived
    session.commit()
    return _article_to_schema(article)


@router.patch("/articles/{article_id}/save", response_model=ArticleOut)
def toggle_save(article_id: int, session: Session = Depends(get_db)):
    """Toggle the saved (read-later) state of an article."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    article.is_saved = not article.is_saved
    session.commit()
    return _article_to_schema(article)


@router.patch("/articles/{article_id}/important", response_model=ArticleOut)
def toggle_important(article_id: int, session: Session = Depends(get_db)):
    """Toggle the important flag on an article."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    article.is_important = not article.is_important
    session.commit()
    return _article_to_schema(article)


@router.post("/articles/{article_id}/open", response_model=ArticleOut)
def record_open(article_id: int, session: Session = Depends(get_db)):
    """Record that the user opened an article. Only records the first open."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    if not article.opened_at:
        article.opened_at = datetime.now(timezone.utc)
        session.commit()
    return _article_to_schema(article)


@router.patch("/articles/{article_id}/rate", response_model=ArticleOut)
def rate_article(article_id: int, payload: RateRequest, session: Session = Depends(get_db)):
    """Set or clear a thumbs-up/down rating on an article."""
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    if payload.rating not in ("up", "down", None):
        raise HTTPException(400, "rating must be 'up', 'down', or null")
    article.user_rating = payload.rating
    session.commit()
    return _article_to_schema(article)


# --- Feedback insights ---

@router.get("/feedback/insights")
def feedback_insights(session: Session = Depends(get_db)):
    """
    Aggregate user engagement signals by topic category.
    Used to surface which topics the user finds most valuable,
    driving future adaptive scoring weight adjustments.
    """
    articles = session.query(Article).filter(Article.score.isnot(None)).all()

    topic_stats: dict[str, dict] = {}
    for a in articles:
        for cat in a.get_categories():
            s = topic_stats.setdefault(cat, {
                "topic": cat, "total": 0, "opened": 0,
                "saved": 0, "important": 0, "rated_up": 0, "rated_down": 0,
            })
            s["total"] += 1
            if a.opened_at:   s["opened"] += 1
            if a.is_saved:    s["saved"] += 1
            if a.is_important: s["important"] += 1
            if a.user_rating == "up":   s["rated_up"] += 1
            if a.user_rating == "down": s["rated_down"] += 1

    # Compute engagement score: weighted sum of positive signals
    for s in topic_stats.values():
        if s["total"] > 0:
            s["engagement_score"] = round(
                (s["opened"] * 1 + s["saved"] * 2 + s["important"] * 3 + s["rated_up"] * 2 - s["rated_down"] * 2)
                / s["total"], 2
            )
        else:
            s["engagement_score"] = 0.0

    ranked = sorted(topic_stats.values(), key=lambda x: x["engagement_score"], reverse=True)
    return {
        "total_articles_with_feedback": sum(
            1 for a in articles if a.opened_at or a.is_saved or a.is_important or a.user_rating
        ),
        "topics": ranked,
    }


@router.post("/feedback/apply-weights")
def apply_feedback_weights(session: Session = Depends(get_db)):
    """
    Compute per-topic engagement scores from accumulated user feedback and
    write them to config/user_weights.yaml. The scorer will load this file
    on the next pipeline run to personalise article scoring.

    Returns a summary of which topics were boosted or penalized.
    """
    from techlens.scoring.feedback_weights import compute_topic_weights, save_weights

    weights = compute_topic_weights(session)
    if not weights:
        return {
            "message": "Not enough feedback data yet. Open, save, or rate some articles first.",
            "topics_computed": 0,
            "boosted": [],
            "penalized": [],
        }

    save_weights(weights)

    boosted = [t for t, s in weights.items() if s >= 0.8]
    penalized = [t for t, s in weights.items() if s <= -0.3]
    return {
        "message": "Adaptive weights saved. They will be applied on the next pipeline run.",
        "topics_computed": len(weights),
        "boosted": sorted(boosted, key=lambda t: -weights[t]),
        "penalized": sorted(penalized, key=lambda t: weights[t]),
        "all_scores": {t: s for t, s in sorted(weights.items(), key=lambda x: -x[1])},
    }


# --- Sources ---

@router.get("/sources", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_db)):
    sources = session.query(Source).order_by(Source.priority.desc()).all()
    return [_source_to_schema(s) for s in sources]


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(payload: SourceCreate, session: Session = Depends(get_db)):
    existing = session.get(Source, payload.id)
    if existing:
        raise HTTPException(409, f"Source '{payload.id}' already exists")
    source = Source(
        id=payload.id,
        name=payload.name,
        feed_url=payload.feed_url,
        home_url=payload.home_url,
        source_type=payload.source_type,
        priority=payload.priority,
        categories=json.dumps(payload.categories),
        polling_frequency_minutes=payload.polling_frequency_minutes,
        enabled=payload.enabled,
    )
    session.add(source)
    session.commit()
    return _source_to_schema(source)


@router.patch("/sources/{source_id}/toggle", response_model=SourceOut)
def toggle_source(source_id: str, session: Session = Depends(get_db)):
    source = session.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    source.enabled = not source.enabled
    session.commit()
    return _source_to_schema(source)


# --- Pipeline ---

@router.post("/pipeline/run", status_code=202)
def trigger_pipeline(background_tasks: BackgroundTasks):
    from techlens.scheduling.scheduler import run_pipeline
    background_tasks.add_task(run_pipeline)
    return {"message": "Pipeline started in background"}


@router.get("/pipeline/status", response_model=PipelineStatus)
def pipeline_status(session: Session = Depends(get_db)):
    from techlens.llm.ollama_provider import get_llm
    from techlens.storage.vector_store import collection_count
    llm = get_llm()
    # Use cumulative counts: how many articles have *reached* each stage.
    # Articles advance through stages, so a summarized/ignored article counts as extracted+scored too.
    _past_extracted = (
        ArticleStatus.extracted, ArticleStatus.scored,
        ArticleStatus.summarized, ArticleStatus.ignored,
    )
    _past_scored = (ArticleStatus.scored, ArticleStatus.summarized, ArticleStatus.ignored)
    return PipelineStatus(
        ollama_available=llm.is_available(),
        total_articles=session.query(Article).count(),
        pending=session.query(Article).filter_by(status=ArticleStatus.pending).count(),
        extracted=session.query(Article).filter(Article.status.in_(_past_extracted)).count(),
        embedded=collection_count(),
        scored=session.query(Article).filter(Article.status.in_(_past_scored)).count(),
        summarized=session.query(Article).filter_by(status=ArticleStatus.summarized).count(),
        ignored=session.query(Article).filter_by(status=ArticleStatus.ignored).count(),
        failed=session.query(Article).filter_by(status=ArticleStatus.failed).count(),
    )


# --- Search (Phase 2) ---

@router.get("/search", response_model=list[ArticleOut])
def semantic_search(
    q: str,
    limit: int = 10,
    session: Session = Depends(get_db),
):
    """
    Semantic search over embedded articles.
    Embeds the query with nomic-embed-text, queries ChromaDB, and returns
    the matching article records from SQLite ordered by similarity.

    Args:
        q:     Natural language search query.
        limit: Maximum number of results (default 10).
    """
    if not q.strip():
        raise HTTPException(400, "Query cannot be empty")

    from techlens.embeddings.ollama_embeddings import get_embedder
    from techlens.storage.vector_store import search

    try:
        embedder = get_embedder()
        query_embedding = embedder.embed(q)
    except Exception as exc:
        raise HTTPException(503, f"Embedding service unavailable: {exc}") from exc

    hits = search(query_embedding, n_results=limit)
    if not hits:
        return []

    article_ids = [h["id"] for h in hits]
    # Preserve similarity order from ChromaDB
    articles_by_id = {
        a.id: a
        for a in session.query(Article).filter(Article.id.in_(article_ids)).all()
    }
    return [
        _article_to_schema(articles_by_id[aid])
        for aid in article_ids
        if aid in articles_by_id
    ]


# --- Phase 3: Trends & Concepts ---

@router.get("/trends", response_model=list[TrendOut])
def list_trends(
    window_days: int | None = None,
    session: Session = Depends(get_db),
):
    """
    Return active trend cards ordered by most recent first.

    Args:
        window_days: Optional filter — pass 7 or 30 to narrow to one window.
    """
    import json as _json

    q = session.query(Trend).filter(Trend.is_active == True)  # noqa: E712
    if window_days is not None:
        q = q.filter(Trend.window_days == window_days)
    trends = q.order_by(Trend.detected_at.desc()).all()
    result = []
    for t in trends:
        try:
            concepts_list = _json.loads(t.concepts)
        except (ValueError, TypeError):
            concepts_list = []
        result.append(TrendOut(
            id=t.id,
            name=t.name,
            summary=t.summary,
            confidence=t.confidence,
            window_days=t.window_days,
            article_count=t.article_count,
            source_count=t.source_count,
            concepts=concepts_list,
            detected_at=t.detected_at,
        ))
    return result


@router.get("/trends/{trend_id}/articles", response_model=list[ArticleOut])
def trend_articles(trend_id: int, session: Session = Depends(get_db)):
    """
    Return the evidence articles that support a trend.

    Args:
        trend_id: Primary key of the trend.
    """
    trend = session.get(Trend, trend_id)
    if not trend:
        raise HTTPException(404, "Trend not found")
    article_ids = [link.article_id for link in trend.article_links]
    articles = session.query(Article).filter(Article.id.in_(article_ids)).all()
    return [_article_to_schema(a) for a in articles]


@router.get("/concepts/top", response_model=list[ConceptOut])
def top_concepts():
    """Return the top 20 concepts by article mention count, sourced from the Kuzu graph."""
    from techlens.storage.graph_store import get_top_concepts
    rows = get_top_concepts(limit=20)
    return [
        ConceptOut(
            name=r["name"],
            concept_type=r["concept_type"],
            article_count=r["article_count"],
            source_count=r["source_count"],
            first_seen_at=r["first_seen_at"],
            last_seen_at=r["last_seen_at"],
        )
        for r in rows
    ]


@router.get("/synthesis", response_model=list[SynthesisOut])
def list_syntheses(session: Session = Depends(get_db)):
    """
    Return active synthesis cards ordered by most recent first.
    JSON columns (unique_perspectives, concepts, article_ids) are deserialised
    before constructing SynthesisOut so the frontend receives typed lists.
    """
    import json as _json

    syntheses = (
        session.query(Synthesis)
        .filter(Synthesis.is_active == True)  # noqa: E712
        .order_by(Synthesis.generated_at.desc())
        .all()
    )
    result = []
    for s in syntheses:
        try:
            unique_perspectives = _json.loads(s.unique_perspectives)
        except (ValueError, TypeError):
            unique_perspectives = []
        try:
            concepts_list = _json.loads(s.concepts)
        except (ValueError, TypeError):
            concepts_list = []
        try:
            article_ids_list = _json.loads(s.article_ids)
        except (ValueError, TypeError):
            article_ids_list = []
        result.append(SynthesisOut(
            id=s.id,
            topic=s.topic,
            summary=s.summary,
            unique_perspectives=unique_perspectives,
            key_insight=s.key_insight,
            source_count=s.source_count,
            article_count=s.article_count,
            concepts=concepts_list,
            article_ids=article_ids_list,
            generated_at=s.generated_at,
        ))
    return result


@router.post("/synthesis/generate", status_code=202)
def trigger_synthesis(background_tasks: BackgroundTasks):
    """
    Trigger cross-source synthesis in the background.
    Queries the knowledge graph for concept clusters covered by 3+ articles from 2+ sources,
    calls the LLM to produce synthesis cards, and persists them to SQLite.
    Returns 202 immediately; synthesis runs asynchronously.
    """
    def _run() -> None:
        from techlens.knowledge_graph.synthesizer import synthesize_all
        from techlens.llm.ollama_provider import get_llm
        from techlens.storage.db import get_session

        llm = get_llm()
        with get_session() as session:
            synthesize_all(session, llm)

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/synthesis/{synthesis_id}/articles", response_model=list[ArticleOut])
def synthesis_articles(synthesis_id: int, session: Session = Depends(get_db)):
    """
    Return the constituent articles for a synthesis card.
    Parses the synthesis's article_ids JSON column and fetches the records from SQLite.

    Args:
        synthesis_id: Primary key of the Synthesis record.
    """
    import json as _json

    synthesis = session.get(Synthesis, synthesis_id)
    if not synthesis:
        raise HTTPException(404, "Synthesis not found")
    try:
        article_ids = _json.loads(synthesis.article_ids)
    except (ValueError, TypeError):
        article_ids = []
    articles = session.query(Article).filter(Article.id.in_(article_ids)).all()
    return [_article_to_schema(a) for a in articles]


# --- Phase 3: Knowledge Map ---

@router.get("/knowledge/map", response_model=KnowledgeMapOut)
def knowledge_map(session: Session = Depends(get_db)):
    """
    Return per-concept knowledge state (seen vs read) for the top 50 concepts.

    For each concept in Kuzu, computes:
      - article_count, source_count from Kuzu node properties.
      - read_count: how many of the concept's articles have opened_at set in SQLite.
      - state: "read" if read_count > 0, else "seen".

    Also returns tier1_gaps: tier1 topic names from profile.yaml that have zero
    articles associated with any concept in Kuzu.

    Returns KnowledgeMapOut with concepts list, tier1_gaps, total_seen, total_read.
    """
    from pathlib import Path

    import yaml

    from techlens.storage.graph_store import get_conn

    # Load top 50 concepts from Kuzu
    conn = get_conn()
    result = conn.execute(
        "MATCH (c:Concept) "
        "RETURN c.name, c.concept_type, c.article_count, c.source_count "
        "ORDER BY c.article_count DESC LIMIT 50"
    )
    concept_rows: list[dict] = []
    while result.has_next():
        row = result.get_next()
        concept_rows.append({
            "name": row[0],
            "concept_type": row[1],
            "article_count": row[2],
            "source_count": row[3],
        })

    # For each concept, query article IDs from Kuzu then check SQLite for opened_at
    knowledge_items: list[ConceptKnowledgeItem] = []
    for cr in concept_rows:
        cname = cr["name"]
        # Get article IDs for this concept from Kuzu
        id_result = conn.execute(
            "MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept {name: $name}) RETURN a.article_id",
            parameters={"name": cname},
        )
        article_ids: list[int] = []
        while id_result.has_next():
            article_ids.append(id_result.get_next()[0])

        # Count how many of those articles have been opened in SQLite
        read_count = 0
        if article_ids:
            read_count = (
                session.query(Article)
                .filter(
                    Article.id.in_(article_ids),
                    Article.opened_at.isnot(None),
                )
                .count()
            )

        state = "read" if read_count > 0 else "seen"
        knowledge_items.append(ConceptKnowledgeItem(
            name=cname,
            concept_type=cr["concept_type"],
            article_count=cr["article_count"],
            source_count=cr["source_count"],
            read_count=read_count,
            state=state,
        ))

    total_seen = len(knowledge_items)
    total_read = sum(1 for item in knowledge_items if item.state == "read")

    # Compute tier1 gaps: tier1 topics from profile.yaml with no Kuzu concept coverage
    tier1_gaps: list[str] = []
    profile_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "profile.yaml"
    if profile_path.exists():
        try:
            with open(profile_path) as f:
                profile = yaml.safe_load(f)
            tier1_topics: list[str] = (
                profile.get("relevance_tiers", {})
                .get("tier1", {})
                .get("topics", [])
            )
            # A topic has coverage if any concept name contains the topic keyword (case-insensitive)
            known_names_lower = {item.name.lower() for item in knowledge_items}
            for topic in tier1_topics:
                topic_keyword = topic.replace("_", " ").lower()
                # Check if any known concept name contains this topic keyword
                has_coverage = any(topic_keyword in name for name in known_names_lower)
                if not has_coverage:
                    tier1_gaps.append(topic)
        except Exception as exc:
            logger.warning("Could not load profile.yaml for tier1 gaps: %s", exc)

    return KnowledgeMapOut(
        concepts=knowledge_items,
        tier1_gaps=tier1_gaps,
        total_seen=total_seen,
        total_read=total_read,
    )


@router.post("/trends/detect", status_code=202)
def trigger_trend_detection(background_tasks: BackgroundTasks):
    """
    Trigger concept extraction + trend detection in the background.
    Returns 202 immediately; detection runs asynchronously.
    """
    def _run() -> None:
        from techlens.knowledge_graph.extractor import extract_all
        from techlens.knowledge_graph.trend_detector import detect_trends
        from techlens.llm.ollama_provider import get_llm
        from techlens.storage.db import get_session

        llm = get_llm()
        with get_session() as session:
            extract_all(session, llm)
            detect_trends(session, llm)

    background_tasks.add_task(_run)
    return {"message": "Trend detection started in background"}


# --- Helpers ---

def _article_to_schema(a: Article) -> ArticleOut:
    return ArticleOut(
        id=a.id,
        title=a.title,
        url=a.url,
        source=a.source_id,
        publication=a.publication,
        score=a.score,
        recommendation=a.recommendation,
        score_rationale=a.score_rationale,
        what_happened=a.summary_what,
        why_it_matters=a.summary_why,
        technical_insights=a.get_technical_insights(),
        architecture_implication=a.summary_architecture,
        tradeoffs=a.summary_tradeoffs,
        estimated_reading_minutes=a.estimated_reading_minutes,
        categories=a.get_categories(),
        published_at=a.published_at,
        is_duplicate=a.is_duplicate,
        is_archived=a.is_archived,
        is_saved=a.is_saved,
        is_important=a.is_important,
        opened_at=a.opened_at,
        user_rating=a.user_rating,
    )


def _source_to_schema(s: Source) -> SourceOut:
    return SourceOut(
        id=s.id,
        name=s.name,
        feed_url=s.feed_url,
        home_url=s.home_url,
        source_type=s.source_type,
        priority=s.priority,
        categories=s.get_categories(),
        enabled=s.enabled,
        last_polled_at=s.last_polled_at,
        failure_count=s.failure_count,
    )
