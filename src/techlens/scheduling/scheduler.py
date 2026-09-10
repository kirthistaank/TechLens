"""
APScheduler-based background scheduler for TechLens.
Runs the full pipeline (collect → extract → score → summarize → concepts → trends → synthesis → digest → email)
once daily at the configured hour. Also exposes run_pipeline() for manual triggers
via the API. Phase 3 adds concept extraction, trend detection, and cross-source synthesis.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from techlens.config import settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_pipeline() -> None:
    """Full pipeline: collect → extract → embed → score → summarize → digest → email."""
    from techlens.digest.daily_digest import build_daily_digest, send_email_digest
    from techlens.embeddings.ollama_embeddings import get_embedder
    from techlens.ingestion.rss_collector import collect_all, load_sources_from_yaml
    from techlens.ingestion.web_collector import collect_all_web
    from techlens.llm.ollama_provider import get_llm
    from techlens.processing.embedder import embed_articles
    from techlens.processing.extractor import process_pending
    from techlens.scoring.relevance_scorer import score_all
    from techlens.storage.db import get_session
    from techlens.summarization.summarizer import summarize_all

    logger.info("Pipeline started")
    llm = get_llm()
    embedder = get_embedder()

    with get_session() as session:
        load_sources_from_yaml(session)
        collect_all(session)            # RSS + Substack feeds
        collect_all_web(session)        # Web listing scrapers (e.g. The Batch)
        process_pending(session)        # Extract content
        embed_articles(session, embedder)  # Embed + semantic dedup (Phase 2)
        score_all(session, llm)         # Score relevance
        summarize_all(session, llm)     # Summarize READ/SKIM

        # Phase 3: knowledge graph
        from techlens.knowledge_graph.extractor import extract_all
        from techlens.knowledge_graph.synthesizer import synthesize_all
        from techlens.knowledge_graph.trend_detector import detect_trends
        extract_all(session, llm)       # Extract concepts from summaries
        detect_trends(session, llm)     # Detect emerging trends
        synthesize_all(session, llm)    # Cross-source synthesis cards

        digest = build_daily_digest(session)
        send_email_digest(digest, session)

    logger.info("Pipeline complete")


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_pipeline,
        trigger="cron",
        hour=settings.pipeline_schedule_hour,
        minute=settings.pipeline_schedule_minute,
        id="daily_pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — pipeline runs daily at %02d:%02d",
        settings.pipeline_schedule_hour,
        settings.pipeline_schedule_minute,
    )


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")
