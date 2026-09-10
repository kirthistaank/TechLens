"""
Daily digest assembler and email sender.
Selects the top-scored articles for today, stores them as a Digest record,
renders an HTML email, and sends it via Gmail SMTP using credentials from settings.
"""

import json
import logging
import smtplib
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from techlens.config import settings
from techlens.storage.models import Article, ArticleStatus, Digest, Recommendation

logger = logging.getLogger(__name__)

_PROFILE_PATH = Path(__file__).parents[3] / "config" / "profile.yaml"


def _max_digest_items() -> int:
    with open(_PROFILE_PATH) as f:
        profile = yaml.safe_load(f)
    return profile["digest"]["max_daily_items"]


def _min_score() -> float:
    with open(_PROFILE_PATH) as f:
        profile = yaml.safe_load(f)
    return profile["digest"]["min_score_for_digest"]


def build_daily_digest(session: Session) -> dict:
    today = date.today().isoformat()

    existing = session.query(Digest).filter_by(date=today, digest_type="daily").first()
    if existing:
        return json.loads(existing.content)

    top_articles = (
        session.query(Article)
        .filter(
            Article.status == ArticleStatus.summarized,
            Article.score >= _min_score(),
            Article.is_duplicate == False,  # noqa: E712
            Article.is_archived == False,  # noqa: E712
        )
        .order_by(Article.score.desc())
        .limit(_max_digest_items())
        .all()
    )

    items = []
    for a in top_articles:
        items.append(
            {
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "source": a.publication,
                "score": a.score,
                "recommendation": a.recommendation,
                "what_happened": a.summary_what,
                "why_it_matters": a.summary_why,
                "technical_insights": a.get_technical_insights(),
                "architecture_implication": a.summary_architecture,
                "tradeoffs": a.summary_tradeoffs,
                "estimated_reading_minutes": a.estimated_reading_minutes,
                "categories": a.get_categories(),
            }
        )

    digest_content = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_collected": session.query(Article).count(),
        "total_scored": session.query(Article).filter(Article.score.isnot(None)).count(),
        "items": items,
    }

    digest = Digest(
        digest_type="daily",
        date=today,
        content=json.dumps(digest_content),
    )
    session.add(digest)
    session.commit()
    logger.info("Daily digest built with %d items", len(items))
    return digest_content


def _render_html(digest: dict) -> str:
    items_html = ""
    for item in digest["items"]:
        badge_color = {"READ": "#16a34a", "SKIM": "#d97706", "IGNORE": "#6b7280"}.get(
            item["recommendation"], "#6b7280"
        )
        insights = "".join(f"<li>{i}</li>" for i in item.get("technical_insights", []))
        items_html += f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:20px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
            <span style="background:{badge_color};color:white;padding:2px 10px;border-radius:4px;
                         font-size:12px;font-weight:bold;">{item["recommendation"]}</span>
            <span style="color:#6b7280;font-size:13px;">{item["source"]}</span>
            <span style="color:#6b7280;font-size:13px;">Score: {item["score"]:.0f}/100</span>
            {f'<span style="color:#6b7280;font-size:13px;">{item["estimated_reading_minutes"]} min</span>'
              if item.get("estimated_reading_minutes") else ""}
          </div>
          <h3 style="margin:0 0 12px;font-size:18px;">
            <a href="{item["url"]}" style="color:#1d4ed8;text-decoration:none;">{item["title"]}</a>
          </h3>
          <p><strong>What happened:</strong> {item.get("what_happened","")}</p>
          <p><strong>Why it matters:</strong> {item.get("why_it_matters","")}</p>
          {"<p><strong>Technical insights:</strong><ul>" + insights + "</ul></p>" if insights else ""}
          {"<p><strong>Architecture:</strong> " + item["architecture_implication"] + "</p>"
            if item.get("architecture_implication") else ""}
          {"<p><strong>Tradeoffs:</strong> " + item["tradeoffs"] + "</p>"
            if item.get("tradeoffs") else ""}
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{{font-family:system-ui,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#111;}}</style>
</head><body>
<h1 style="border-bottom:2px solid #1d4ed8;padding-bottom:8px;">
  TechLens Daily Brief — {digest["date"]}
</h1>
<p style="color:#6b7280;">
  {len(digest["items"])} items selected from {digest["total_scored"]} scored articles.
</p>
{items_html}
<hr style="margin-top:40px;border-color:#e5e7eb;">
<p style="color:#9ca3af;font-size:12px;">Generated by TechLens · Local AI Intelligence Agent</p>
</body></html>"""


def send_email_digest(digest: dict, session: Session) -> bool:
    if not settings.digest_email_enabled:
        logger.info("Email digest disabled — skipping")
        return False
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP credentials not configured — skipping email")
        return False

    html = _render_html(digest)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"TechLens Daily Brief — {digest['date']} ({len(digest['items'])} items)"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.digest_email_to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, settings.digest_email_to, msg.as_string())

        today = date.today().isoformat()
        record = session.query(Digest).filter_by(date=today, digest_type="daily").first()
        if record:
            record.email_sent = True
            session.commit()

        logger.info("Digest email sent to %s", settings.digest_email_to)
        return True
    except Exception as exc:
        logger.error("Failed to send digest email: %s", exc)
        return False
