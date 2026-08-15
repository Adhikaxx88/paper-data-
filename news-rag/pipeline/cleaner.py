"""Clean raw scraped articles: strip markup, normalize dates, filter short content."""
import json
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from loguru import logger

from config import DATA_CLEAN_DIR, DATA_RAW_DIR, MIN_CONTENT_LENGTH

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPECIAL_CHARS_RE = re.compile(r"[^\w\s.,!?%\-À-ɏ]")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML tags from text.

    Args:
        text: Raw text possibly containing HTML markup.

    Returns:
        Text with tags removed.
    """
    return _HTML_TAG_RE.sub(" ", text)


def normalize_text(text: str) -> str:
    """Strip HTML, remove special characters, and collapse whitespace.

    Args:
        text: Raw article text.

    Returns:
        Cleaned, whitespace-normalized text.
    """
    text = strip_html(text)
    text = _SPECIAL_CHARS_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_date(raw_date: str) -> Optional[str]:
    """Convert a Google News RFC-822 date string to ISO 8601 (YYYY-MM-DD).

    Args:
        raw_date: Date string as returned by the scraper (e.g. "Wed, 15 Aug 2026 09:00:00 GMT").

    Returns:
        ISO date string, or None if the date could not be parsed.
    """
    if not raw_date:
        return None
    try:
        return parsedate_to_datetime(raw_date).date().isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(raw_date).date().isoformat()
        except ValueError:
            logger.warning(f"Could not parse date: {raw_date}")
            return None


def clean_article(article: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Clean a single article record.

    Args:
        article: Raw article dict with source, title, content, date, url, category.

    Returns:
        Cleaned article dict, or None if it fails the minimum content length filter.
    """
    content = normalize_text(article.get("content", ""))
    if len(content) < MIN_CONTENT_LENGTH:
        return None

    return {
        "source": normalize_text(article.get("source", "")),
        "title": normalize_text(article.get("title", "")),
        "content": content,
        "date": normalize_date(article.get("date", "")),
        "url": article.get("url", ""),
        "category": article.get("category", ""),
    }


def run(raw_file: Optional[str] = None) -> str:
    """Clean raw article files and save deduplicated results to data/clean/.

    Args:
        raw_file: Optional specific raw JSON file to process. Defaults to
            processing every file in data/raw/.

    Returns:
        Path to the written cleaned JSON file.
    """
    os.makedirs(DATA_CLEAN_DIR, exist_ok=True)
    files = (
        [raw_file]
        if raw_file
        else [os.path.join(DATA_RAW_DIR, f) for f in os.listdir(DATA_RAW_DIR) if f.endswith(".json")]
    )

    seen_urls: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    dropped = 0

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                articles = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read raw file {path}: {e}")
            continue

        for article in articles:
            url = article.get("url", "")
            if not url or url in seen_urls:
                continue
            result = clean_article(article)
            if result is None:
                dropped += 1
                continue
            seen_urls.add(url)
            cleaned.append(result)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    out_path = os.path.join(DATA_CLEAN_DIR, f"clean_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    logger.info(f"Cleaned {len(cleaned)} articles ({dropped} dropped as too short) -> {out_path}")
    return out_path


if __name__ == "__main__":
    run()
