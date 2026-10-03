"""Split clean_articles content (read from PostgreSQL) into overlapping token-based chunks."""
import uuid
from datetime import date, datetime
from typing import Any, Optional

import tiktoken
from loguru import logger

from config import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS
from db.postgres import get_all_clean_articles, get_connection

_encoding = tiktoken.get_encoding("cl100k_base")


def _derive_chunk_id(url: str, chunk_index: int) -> uuid.UUID:
    """Derive a deterministic chunk UUID from an article's URL and chunk index.

    A URL-derived UUID keeps chunk ids stable across pipeline re-runs (the
    same article always yields the same chunk ids), which is what makes
    embedding idempotent.

    Args:
        url: The article's canonical URL.
        chunk_index: The chunk's position within the article.

    Returns:
        A UUID deterministically derived from url and chunk_index.
    """
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{chunk_index}")


def _format_date(published: Any) -> Optional[str]:
    """Convert a clean_articles.published value into an ISO date string.

    psycopg2 returns PostgreSQL TIMESTAMPTZ columns as datetime objects,
    but pipeline/embedder.py's date parsing expects an ISO 8601 string.

    Args:
        published: A datetime, date, string, or None, as returned by psycopg2.

    Returns:
        ISO date string (YYYY-MM-DD), or None if published is empty.
    """
    if not published:
        return None
    if isinstance(published, datetime):
        return published.date().isoformat()
    if isinstance(published, date):
        return published.isoformat()
    return str(published)


def split_tokens(text: str, chunk_size: int = CHUNK_SIZE_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
    """Split text into overlapping chunks measured in tokens.

    Args:
        text: The article content to split.
        chunk_size: Target chunk size in tokens.
        overlap: Number of tokens to overlap between consecutive chunks.

    Returns:
        List of chunk strings, decoded back to text.
    """
    tokens = _encoding.encode(text)
    if not tokens:
        return []

    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(tokens), step):
        window = tokens[start : start + chunk_size]
        chunks.append(_encoding.decode(window))
        if start + chunk_size >= len(tokens):
            break
    return chunks


def _split_into_chunks(article: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk a single clean_articles row into embed-ready records.

    Field names match what pipeline/embedder.py and vectorization/qdrant_store.py
    already expect: `date` (not `published`) and `category` (not `topic_category`).

    Args:
        article: A clean_articles row (dict) as returned by get_all_clean_articles,
            with id, url, title, content, published, source, topic_category, sub_area,
            keyword.

    Returns:
        List of chunk dicts carrying chunk_id, article_id, source, title, date,
        category, sub_area, keyword, url, chunk_index, and chunk_text.
    """
    article_id = str(article["id"])
    url = article["url"]
    pieces = split_tokens(article["content"])
    published = _format_date(article.get("published"))

    return [
        {
            "chunk_id": str(_derive_chunk_id(url, idx)),
            "article_id": article_id,
            "source": article.get("source"),
            "title": article.get("title"),
            "date": published,
            "category": article.get("topic_category"),
            "sub_area": article.get("sub_area"),
            "keyword": article.get("keyword"),
            "language": article.get("language", "en"),
            "url": url,
            "chunk_index": idx,
            "chunk_text": piece,
        }
        for idx, piece in enumerate(pieces)
    ]


def chunk_articles() -> list[dict[str, Any]]:
    """Read every clean_articles row from PostgreSQL and split it into chunks.

    Returns:
        List of chunk dicts, ready to pass to pipeline.embedder.embed_and_store.
    """
    conn = get_connection()
    try:
        articles = get_all_clean_articles(conn)
    finally:
        conn.close()

    all_chunks: list[dict[str, Any]] = []
    for article in articles:
        all_chunks.extend(_split_into_chunks(article))

    logger.info(f"Chunked {len(all_chunks)} chunks from {len(articles)} articles")
    return all_chunks


if __name__ == "__main__":
    chunk_articles()
