"""Split cleaned article content into overlapping token-based chunks."""
import json
import os
import uuid
from datetime import datetime
from typing import Any, Optional

import tiktoken
from loguru import logger

from config import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS, DATA_CHUNKS_DIR, DATA_CLEAN_DIR

_encoding = tiktoken.get_encoding("cl100k_base")


def derive_article_id(url: str) -> uuid.UUID:
    """Derive a deterministic article UUID from its URL.

    URL-derived UUIDs keep article and chunk ids stable across pipeline
    re-runs, which is what makes chunking and embedding idempotent.

    Args:
        url: The article's canonical URL.

    Returns:
        A UUID deterministically derived from the URL.
    """
    return uuid.uuid5(uuid.NAMESPACE_URL, url)


def derive_chunk_id(article_id: uuid.UUID, chunk_index: int) -> uuid.UUID:
    """Derive a deterministic chunk UUID from its article id and index.

    Args:
        article_id: The parent article's UUID.
        chunk_index: The chunk's position within the article.

    Returns:
        A UUID deterministically derived from article_id and chunk_index.
    """
    return uuid.uuid5(article_id, str(chunk_index))


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


def chunk_article(article: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk a single cleaned article into embed-ready records.

    Args:
        article: Cleaned article dict with source, title, content, date, url, category.

    Returns:
        List of chunk dicts carrying chunk_id, article_id, source, title, date,
        category, url, chunk_index, and chunk_text.
    """
    article_id = derive_article_id(article["url"])
    pieces = split_tokens(article["content"])

    return [
        {
            "chunk_id": str(derive_chunk_id(article_id, idx)),
            "article_id": str(article_id),
            "source": article["source"],
            "title": article["title"],
            "date": article["date"],
            "category": article["category"],
            "url": article["url"],
            "chunk_index": idx,
            "chunk_text": piece,
        }
        for idx, piece in enumerate(pieces)
    ]


def run(clean_file: Optional[str] = None) -> str:
    """Chunk all (or one) cleaned article file(s) and save chunk records as JSON.

    Args:
        clean_file: Optional specific cleaned JSON file to process. Defaults to
            processing every file in data/clean/.

    Returns:
        Path to the written chunks JSON file.
    """
    os.makedirs(DATA_CHUNKS_DIR, exist_ok=True)
    files = (
        [clean_file]
        if clean_file
        else [os.path.join(DATA_CLEAN_DIR, f) for f in os.listdir(DATA_CLEAN_DIR) if f.endswith(".json")]
    )

    all_chunks: list[dict[str, Any]] = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                articles = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read cleaned file {path}: {e}")
            continue

        for article in articles:
            chunks = chunk_article(article)
            all_chunks.extend(chunks)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    out_path = os.path.join(DATA_CHUNKS_DIR, f"chunks_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(all_chunks)} chunks to {out_path}")
    return out_path


if __name__ == "__main__":
    run()
