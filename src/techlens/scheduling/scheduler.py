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
_pipeline_running: bool = False


def is_pipeline_running() -> bool:
    """Return True if the pipeline is currently executing."""
    return _pipeline_running


def run_pipeline() -> None:
    """Full pipeline: collect → extract → embed → score → summarize → digest → email."""
    global _pipeline_running
    if _pipeline_running:
        logger.warning("Pipeline already running — skipping duplicate trigger")
        return
    _pipeline_running = True

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

    try:
        with get_session() as session:
            from techlens.storage.cleanup import purge_old_articles
            purge_old_articles(session)
            load_sources_from_yaml(session)
            collect_all(session)
            collect_all_web(session)
            process_pending(session)
            embed_articles(session, embedder)
            score_all(session, llm)
            summarize_all(session, llm)

            from techlens.knowledge_graph.extractor import extract_all
            from techlens.knowledge_graph.synthesizer import synthesize_all
            from techlens.knowledge_graph.trend_detector import detect_trends
            extract_all(session, llm)
            detect_trends(session, llm)
            synthesize_all(session, llm)

            digest = build_daily_digest(session)
            send_email_digest(digest, session)

        logger.info("Pipeline complete")
    except Exception:
        logger.exception("Pipeline failed")
    finally:
        _pipeline_running = False


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
