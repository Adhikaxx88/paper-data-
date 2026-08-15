"""Scrape Google News articles by keyword and save raw JSON to data/raw/."""
import json
import os
from datetime import datetime
from typing import Any

from gnews import GNews
from loguru import logger

from config import ARTICLES_PER_KEYWORD, DATA_RAW_DIR, NEWS_KEYWORDS


def _load_existing_urls() -> set[str]:
    """Collect URLs already present in previously saved raw JSON files.

    Scanning prior output lets re-runs skip articles already scraped,
    keeping the scraper idempotent across pipeline runs.

    Returns:
        Set of article URLs already saved under data/raw/.
    """
    urls: set[str] = set()
    if not os.path.isdir(DATA_RAW_DIR):
        return urls
    for filename in os.listdir(DATA_RAW_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(DATA_RAW_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                articles = json.load(f)
            urls.update(a["url"] for a in articles if a.get("url"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping unreadable raw file {path}: {e}")
    return urls


def scrape_keyword(client: GNews, keyword: str, existing_urls: set[str]) -> list[dict[str, Any]]:
    """Scrape Google News articles for a single keyword.

    Args:
        client: A configured GNews client.
        keyword: Search term used both as the query and the article category.
        existing_urls: URLs already scraped; matches are skipped and this set is updated in place.

    Returns:
        List of article dicts with source, title, content, date, url, category.
    """
    results: list[dict[str, Any]] = []
    try:
        raw_results = client.get_news(keyword)
    except Exception as e:
        logger.error(f"Failed to fetch news for keyword '{keyword}': {e}")
        return results

    for item in raw_results:
        url = item.get("url", "")
        if not url or url in existing_urls:
            continue

        content = item.get("description", "") or ""
        try:
            full_article = client.get_full_article(url)
            if full_article and full_article.text:
                content = full_article.text
        except Exception as e:
            logger.warning(f"Could not fetch full article text for {url}: {e}")

        results.append(
            {
                "source": (item.get("publisher") or {}).get("title", "unknown"),
                "title": item.get("title", ""),
                "content": content,
                "date": item.get("published date", ""),
                "url": url,
                "category": keyword,
            }
        )
        existing_urls.add(url)
    return results


def run() -> str:
    """Scrape all configured keywords and save newly found articles as raw JSON.

    Returns:
        Path to the written JSON file.
    """
    os.makedirs(DATA_RAW_DIR, exist_ok=True)
    existing_urls = _load_existing_urls()
    client = GNews(language="id", max_results=ARTICLES_PER_KEYWORD)
    all_articles: list[dict[str, Any]] = []

    for keyword in NEWS_KEYWORDS:
        logger.info(f"Scraping Google News for keyword: {keyword}")
        articles = scrape_keyword(client, keyword, existing_urls)
        logger.info(f"Found {len(articles)} new articles for '{keyword}'")
        all_articles.extend(articles)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    out_path = os.path.join(DATA_RAW_DIR, f"scrape_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(all_articles)} new articles to {out_path}")
    return out_path


if __name__ == "__main__":
    run()
