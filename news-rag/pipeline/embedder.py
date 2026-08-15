"""Embed chunks with OpenAI and store vectors in Qdrant, text in PostgreSQL."""
import json
import os
import uuid
from datetime import date, datetime
from typing import Any, Optional

from loguru import logger
from openai import OpenAI

from config import DATA_CHUNKS_DIR, EMBEDDING_MODEL, OPENAI_API_KEY
from db import postgres, qdrant_client

_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Return a lazily-initialized, module-level OpenAI client.

    Returns:
        A configured OpenAI client instance.
    """
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single string using the configured OpenAI embedding model.

    Args:
        text: Text to embed.

    Returns:
        The embedding vector.
    """
    response = get_openai_client().embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def _parse_date(raw_date: Optional[str]) -> Optional[date]:
    """Parse an ISO date string into a date object.

    Args:
        raw_date: ISO 8601 date string (YYYY-MM-DD), or None.

    Returns:
        A date object, or None if raw_date is missing/unparseable.
    """
    if not raw_date:
        return None
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


def index_chunk(chunk: dict[str, Any]) -> bool:
    """Embed and store a single chunk, skipping it if already indexed.

    Args:
        chunk: Chunk dict as produced by pipeline.chunker.

    Returns:
        True if the chunk was newly indexed, False if it was already present.
    """
    chunk_id = uuid.UUID(chunk["chunk_id"])
    article_id = uuid.UUID(chunk["article_id"])

    if postgres.chunk_exists(chunk_id) and qdrant_client.point_exists(chunk_id):
        return False

    postgres.upsert_article(
        source=chunk["source"],
        title=chunk["title"],
        article_date=_parse_date(chunk["date"]),
        url=chunk["url"],
        category=chunk["category"],
        article_id=article_id,
    )
    postgres.insert_chunk(chunk_id, article_id, chunk["chunk_index"], chunk["chunk_text"])

    vector = embed_text(chunk["chunk_text"])
    qdrant_client.upsert_point(
        chunk_id,
        vector,
        payload={
            "chunk_id": str(chunk_id),
            "article_id": str(article_id),
            "title": chunk["title"],
            "source": chunk["source"],
            "date": chunk["date"],
            "category": chunk["category"],
        },
    )
    return True


def run(chunks_file: Optional[str] = None) -> dict[str, int]:
    """Embed and store all (or one) chunk file(s) into Qdrant and PostgreSQL.

    Args:
        chunks_file: Optional specific chunks JSON file to process. Defaults to
            processing every file in data/chunks/.

    Returns:
        Summary dict with counts of processed, indexed, and skipped chunks.
    """
    postgres.init_schema()
    qdrant_client.init_collection()

    files = (
        [chunks_file]
        if chunks_file
        else [os.path.join(DATA_CHUNKS_DIR, f) for f in os.listdir(DATA_CHUNKS_DIR) if f.endswith(".json")]
    )

    indexed = 0
    skipped = 0
    processed = 0

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read chunks file {path}: {e}")
            continue

        for chunk in chunks:
            processed += 1
            try:
                if index_chunk(chunk):
                    indexed += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Failed to index chunk {chunk.get('chunk_id')}: {e}")

    logger.info(f"Embedding complete: {processed} processed, {indexed} indexed, {skipped} already indexed")
    return {"processed": processed, "indexed": indexed, "skipped": skipped}


if __name__ == "__main__":
    run()
