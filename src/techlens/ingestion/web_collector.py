"""
Web listing collector — scrapes a paginated listing page to discover article URLs.
Used for sources that don't offer RSS (e.g. DeepLearning.AI The Batch).
Only URL discovery happens here; full content extraction is handled by extractor.py.
"""

import hashlib
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

from techlens.storage.models import Article, Source

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _url_hash(url: str) -> str:
    """Return a SHA-256 hex digest of the URL for deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()


def _extract_links(html: str, base_url: str, pattern: str) -> list[str]:
    """
    Extract absolute article URLs from HTML using a regex pattern.

    Args:
        html: Raw HTML of the listing page.
        base_url: Base URL of the site, used to resolve relative hrefs.
        pattern: Regex pattern matching article href values in the HTML.

    Returns:
        Deduplicated list of absolute article URLs in discovery order.
    """
    raw_links = re.findall(pattern, html)
    seen: set[str] = set()
    results: list[str] = []
    for link in raw_links:
        absolute = urljoin(base_url, link)
        if absolute not in seen:
            seen.add(absolute)
            results.append(absolute)
    return results


def collect_web_source(source: Source, session) -> int:
    """
    Fetch a listing page for a web-type source and insert new article stubs.

    Reads listing_url and link_pattern from the source record.
    For each discovered URL not already in the DB, inserts an Article with
    status=pending so extractor.py can fetch the full content on the next run.

    Args:
        source: A Source record with source_type='web'.
        session: Active SQLAlchemy session (caller owns commit).

    Returns:
        Number of new article stubs inserted.
    """
    listing_url = getattr(source, "listing_url", None) or source.home_url
    link_pattern = getattr(source, "link_pattern", None)

    if not link_pattern:
        logger.warning("Web source %s has no link_pattern — skipping", source.id)
        return 0

    logger.info("Fetching listing page for %s: %s", source.name, listing_url)

    try:
        resp = httpx.get(listing_url, headers=_HEADERS, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to fetch listing page %s: %s", listing_url, exc)
        source.failure_count += 1
        session.commit()
        return 0

    from techlens.config import settings

    parsed = urlparse(listing_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    all_links = _extract_links(resp.text, base, link_pattern)
    # Cap to most-recent N links — listing pages show newest first
    links = all_links[: settings.web_source_max_articles]
    logger.info(
        "Found %d candidate links for %s, taking newest %d",
        len(all_links), source.name, len(links),
    )

    new_count = 0
    for url in links:
        uhash = _url_hash(url)
        if session.query(Article).filter_by(url_hash=uhash).first():
            continue

        # Derive a title stub from the URL slug; extractor replaces it with the real title
        slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()

        article = Article(
            url=url,
            url_hash=uhash,
            title=slug[:500],
            publication=source.name,
            source_id=source.id,
        )
        session.add(article)
        new_count += 1

    source.failure_count = 0
    logger.info("Inserted %d new article stubs from %s", new_count, source.name)
    return new_count


def collect_all_web(session) -> int:
    """
    Run web listing collection for all enabled web-type sources.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Total new article stubs inserted across all web sources.
    """
    sources = session.query(Source).filter_by(enabled=True, source_type="web").all()
    total = sum(collect_web_source(s, session) for s in sources)
    session.commit()
    logger.info("Web collection complete — %d new article stubs total", total)
    return total
