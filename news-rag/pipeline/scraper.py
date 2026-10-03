"""Scrape Google News via RSS and insert articles directly into PostgreSQL raw_articles."""
import random
import socket
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import feedparser
import trafilatura
from googlenewsdecoder import gnewsdecoder
from loguru import logger

from config import (
    GOOGLE_NEWS_RSS_TEMPLATE,
    GOOGLE_NEWS_RSS_TEMPLATE_ID,
    MAX_ARTICLE_AGE_DAYS,
    MAX_ARTICLES_PER_TOPIC,
    MIN_CONTENT_LENGTH,
    SCRAPE_DELAY_MAX_SECONDS,
    SCRAPE_DELAY_MIN_SECONDS,
    TOPIC_QUERIES,
    TOPIC_QUERIES_ID,
    USER_AGENTS,
)
from db.postgres import get_connection, insert_raw_article


def _fetch_rss(query: str, rss_template: str = GOOGLE_NEWS_RSS_TEMPLATE) -> list[Any]:
    """Fetch Google News RSS results for a search query.

    Args:
        query: Free-text search query.
        rss_template: Google News RSS URL template to use (controls language/region).

    Returns:
        List of feedparser entries, or an empty list on failure.
    """
    print(f"[DEBUG] Fetching RSS for query: {query}", flush=True)
    url = rss_template.format(query=urllib.parse.quote(query))
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(30)
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": random.choice(USER_AGENTS)})
    except Exception as e:
        logger.error(f"Failed to fetch RSS for query '{query}': {e}")
        return []
    finally:
        socket.setdefaulttimeout(old_timeout)

    print(f"[DEBUG] RSS fetched, got {len(feed.entries)} entries", flush=True)

    if feed.bozo:
        logger.warning(f"Malformed/blocked RSS feed for query '{query}': {feed.bozo_exception}")
    if not feed.entries:
        logger.warning(f"No entries returned for query '{query}'")
    return list(feed.entries)


def _filter_by_age(entries: list[Any], max_age_days: int) -> list[Any]:
    """Drop entries older than max_age_days.

    Args:
        entries: feedparser entries.
        max_age_days: Maximum article age in days; entries without a parsable
            publish date are kept (age can't be determined, so don't drop them).

    Returns:
        Filtered list of entries.
    """
    now = datetime.now(timezone.utc)
    kept = []
    for entry in entries:
        parsed = getattr(entry, "published_parsed", None)
        if not parsed:
            kept.append(entry)
            continue
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        if (now - published).days <= max_age_days:
            kept.append(entry)
    return kept


def _sort_by_date(entries: list[Any]) -> list[Any]:
    """Sort entries newest-first, entries without a date last.

    Args:
        entries: feedparser entries.

    Returns:
        Sorted list of entries.
    """
    return sorted(entries, key=lambda e: getattr(e, "published_parsed", None) or (), reverse=True)


def _decode_url(google_url: str) -> str:
    """Resolve a Google News redirect URL to the underlying publisher URL.

    Args:
        google_url: The `link` field from a Google News RSS entry.

    Returns:
        The decoded publisher URL, or the original URL if decoding fails.
    """
    try:
        result = gnewsdecoder(google_url)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as e:
        logger.warning(f"Could not decode Google News URL {google_url}: {e}")
        return google_url
    logger.warning(f"Falling back to raw Google News URL (decode unsuccessful): {google_url}")
    return google_url


def _extract_content(url: str) -> str:
    """Download and extract the main article text from a URL.

    Args:
        url: The publisher article URL.

    Returns:
        Extracted article text, or an empty string on failure.
    """
    try:
        print(f"[DEBUG] Fetching content from: {url}", flush=True)
        downloaded = trafilatura.fetch_url(url)
        print(f"[DEBUG] Content fetched, length: {len(downloaded) if downloaded else 0}", flush=True)
        if downloaded is None:
            return ""
        extracted = trafilatura.extract(
            downloaded, include_comments=False, include_tables=False, no_fallback=False
        )
        return extracted or ""
    except Exception as e:
        logger.warning(f"Could not extract content from {url}: {e}")
        return ""


def _normalize_date(entry: Any) -> Optional[datetime]:
    """Convert a feed entry's published date into a timezone-aware datetime.

    Args:
        entry: feedparser entry.

    Returns:
        A UTC datetime, or None if the entry has no parsable date.
    """
    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _extract_source(entry: Any) -> str:
    """Extract the publisher name from a feed entry.

    Args:
        entry: feedparser entry.

    Returns:
        The publisher name, or "unknown" if not present.
    """
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", None):
        return source.title
    title = getattr(entry, "title", "") or ""
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "unknown"


def _polite_delay() -> None:
    """Sleep a random, human-ish interval between requests to avoid rate limiting."""
    time.sleep(random.uniform(SCRAPE_DELAY_MIN_SECONDS, SCRAPE_DELAY_MAX_SECONDS))


def _scrape_topic_queries(
    topic_queries: dict[str, dict[str, list[dict]]],
    rss_template: str,
    language: str,
    max_per_query: int,
    max_age_days: int,
) -> dict[str, int]:
    """Scrape every query in a topic_queries dict and insert new articles into PostgreSQL.

    Args:
        topic_queries: Mapping of category name to a mapping of sub_area name
            to a list of {"keyword": ...} dicts.
        rss_template: Google News RSS URL template to use (controls language/region).
        language: Language code to tag inserted articles with (e.g. "en", "id").
        max_per_query: Maximum number of newly-inserted articles per query.
        max_age_days: Drop RSS entries older than this many days.

    Returns:
        Summary dict: scraped, inserted, skipped_duplicate, skipped_short.
    """
    scraped, inserted, dup, short = 0, 0, 0, 0

    for category, sub_areas in topic_queries.items():
        for sub_area, query_entries in sub_areas.items():
            for query_entry in query_entries:
                query = query_entry["keyword"]

                entries = _fetch_rss(query, rss_template)
                entries = _filter_by_age(entries, max_age_days)
                entries = _sort_by_date(entries)

                conn = get_connection()
                try:
                    count = 0
                    examined = 0
                    for entry in entries:
                        if count >= max_per_query:
                            break
                        if examined >= max_per_query * 3:
                            break
                        examined += 1

                        try:
                            link = getattr(entry, "link", None)
                            if not link:
                                logger.warning(f"Skipping entry with no link for query '{query}'")
                                continue

                            print(f"[DEBUG] Decoding URL: {getattr(entry, 'link', 'NO_LINK')}", flush=True)
                            url = _decode_url(link)
                            print(f"[DEBUG] Decoded to: {url}", flush=True)
                            content = _extract_content(url)
                            scraped += 1

                            if len(content) < MIN_CONTENT_LENGTH:
                                short += 1
                                _polite_delay()
                                continue

                            article = {
                                "url": url,
                                "title": getattr(entry, "title", ""),
                                "content": content,
                                "published": _normalize_date(entry),
                                "source": _extract_source(entry),
                                "topic_category": category,
                                "sub_area": sub_area,
                                "search_query": query,
                                "keyword": query,
                                "language": language,
                            }

                            result = insert_raw_article(conn, article)
                            if result:
                                inserted += 1
                                count += 1
                            else:
                                dup += 1

                            _polite_delay()
                        except Exception as e:
                            logger.error(f"Error processing entry for query '{query}': {e}")
                            continue
                finally:
                    conn.close()

    return {"scraped": scraped, "inserted": inserted, "skipped_duplicate": dup, "skipped_short": short}


def fetch_and_store(
    topic_queries: dict[str, dict[str, list[dict]]] = TOPIC_QUERIES,
    max_per_query: int = MAX_ARTICLES_PER_TOPIC,
    max_age_days: int = MAX_ARTICLE_AGE_DAYS,
) -> dict[str, int]:
    """Scrape every configured query (English and Indonesian) and insert new
    articles directly into PostgreSQL.

    Args:
        topic_queries: Mapping of category name to a mapping of sub_area name
            to a list of {"keyword": ...} dicts, used for the English pass.
        max_per_query: Maximum number of newly-inserted articles per query.
        max_age_days: Drop RSS entries older than this many days.

    Returns:
        Summary dict: scraped, inserted, skipped_duplicate, skipped_short.
    """
    # TEMP: English scrape disabled, only running Indonesian pass.
    # en_summary = _scrape_topic_queries(
    #     topic_queries, GOOGLE_NEWS_RSS_TEMPLATE, "en", max_per_query, max_age_days
    # )
    id_summary = _scrape_topic_queries(
        TOPIC_QUERIES_ID, GOOGLE_NEWS_RSS_TEMPLATE_ID, "id", max_per_query, max_age_days
    )

    summary = {
        key: id_summary[key]
        for key in ("scraped", "inserted", "skipped_duplicate", "skipped_short")
    }
    logger.info(f"Scrape complete: {summary}")
    return summary


if __name__ == "__main__":
    fetch_and_store()
