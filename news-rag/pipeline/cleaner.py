"""Clean raw_articles rows in PostgreSQL and insert the results into clean_articles."""
import re
from typing import Any, Optional

from loguru import logger

from config import MIN_CONTENT_LENGTH
from db.postgres import get_connection, get_uncleaned_raw_articles, insert_clean_article, url_exists_in_clean

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPECIAL_CHARS_RE = re.compile(r"[^\w\s.,!?%\-À-ɏ]")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    """Strip HTML, remove special characters, and collapse whitespace.

    Args:
        text: Raw text.

    Returns:
        Cleaned, whitespace-normalized text.
    """
    text = _HTML_TAG_RE.sub(" ", text)
    text = _SPECIAL_CHARS_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _is_indonesia_relevant(article: dict) -> bool:
    """Check whether an article's title, url, or content mentions Indonesia.

    Args:
        article: A dict with title, url, and content fields.

    Returns:
        True if "indonesia" (case-insensitive) appears in any of those fields.
    """
    title = article.get("title") or ""
    url = article.get("url") or ""
    content = article.get("content") or ""
    return "indonesia" in title.lower() or "indonesia" in url.lower() or "indonesia" in content.lower()


def _clean_article(article: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Apply cleaning rules to a raw_articles row.

    Rules: title, url, and content must be present and non-empty; content
    must be at least MIN_CONTENT_LENGTH characters after normalization;
    whitespace and HTML markup are stripped from text fields.

    Args:
        article: A raw_articles row (dict) as returned by get_uncleaned_raw_articles.

    Returns:
        A clean_articles-ready dict, or None if the article doesn't pass the rules.
    """
    title = article.get("title") or ""
    url = article.get("url") or ""
    raw_content = article.get("content") or ""
    if not title.strip() or not url.strip() or not raw_content.strip():
        return None

    content = _normalize_text(raw_content)
    if len(content) < MIN_CONTENT_LENGTH:
        return None

    return {
        "raw_id": article["id"],
        "url": url,
        "title": _normalize_text(title),
        "content": content,
        "published": article.get("published"),
        "source": _normalize_text(article.get("source") or ""),
        "topic_category": article.get("topic_category"),
        "sub_area": article.get("sub_area"),
        "keyword": article.get("keyword"),
        "language": article.get("language", "en"),
    }


def clean_and_store() -> dict[str, int]:
    """Clean every not-yet-cleaned raw_articles row and insert it into clean_articles.

    Skips articles whose URL already exists in clean_articles (duplicate detection).

    Returns:
        Summary dict: processed, inserted, skipped, duplicates.
    """
    conn = get_connection()
    try:
        raw_articles = get_uncleaned_raw_articles(conn)

        processed, inserted, skipped, duplicates, skipped_not_indonesia = 0, 0, 0, 0, 0
        for article in raw_articles:
            processed += 1
            cleaned = _clean_article(article)
            if cleaned is None:
                skipped += 1
                continue

            if not _is_indonesia_relevant(cleaned):
                skipped_not_indonesia += 1
                continue

            if url_exists_in_clean(conn, cleaned["url"]):
                logger.debug(f"Duplicate skipped: {cleaned['url']}")
                duplicates += 1
                continue

            result = insert_clean_article(conn, cleaned)
            inserted += 1 if result else 0
    finally:
        conn.close()

    summary = {
        "processed": processed,
        "inserted": inserted,
        "skipped": skipped,
        "duplicates": duplicates,
        "skipped_not_indonesia": skipped_not_indonesia,
    }
    logger.info(f"Clean complete: {summary}")
    return summary


if __name__ == "__main__":
    clean_and_store()