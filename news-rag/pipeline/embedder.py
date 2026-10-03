"""Embed chunks natively (BGE dense + BM25 sparse) and store vectors+text in Qdrant, text in PostgreSQL."""
import json
import os
import uuid
from datetime import date
from typing import Any, Optional

from loguru import logger

from config import DATA_CHUNKS_DIR
from db import postgres
from vectorization.embedder import encode_passage, encode_sparse
from vectorization.qdrant_store import init_collection, point_exists, upsert_chunks


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


def _store_in_postgres(chunk: dict[str, Any]) -> None:
    """Persist a chunk's text and parent article metadata in PostgreSQL.

    PostgreSQL is used for chat history and metadata lookup only — retrieval
    reads chunk_text directly from the Qdrant payload instead.

    Args:
        chunk: Chunk dict as produced by pipeline.chunker.
    """
    article_id = chunk["article_id"]
    chunk_id = chunk["chunk_id"]
    postgres.upsert_article(
        source=chunk["source"],
        title=chunk["title"],
        article_date=_parse_date(chunk["date"]),
        url=chunk["url"],
        category=chunk["category"],
        article_id=article_id,
    )
    postgres.insert_chunk(
        chunk_id,
        article_id,
        chunk["chunk_index"],
        chunk["chunk_text"],
        keyword=chunk.get("keyword"),
    )


def embed_and_store(chunks: list[dict[str, Any]]) -> dict[str, int]:
    """Embed a batch of chunks and store them in Qdrant (vectors + text) and PostgreSQL.

    Skips chunks already indexed in Qdrant so re-running the pipeline is safe.

    Args:
        chunks: Chunk dicts as produced by pipeline.chunker.

    Returns:
        Summary dict with counts of processed, indexed, and skipped chunks.
    """
    init_collection()

    new_chunks = [c for c in chunks if not point_exists(uuid.UUID(c["chunk_id"]))]
    skipped = len(chunks) - len(new_chunks)

    if new_chunks:
        total = len(new_chunks)
        for i, chunk in enumerate(new_chunks, start=1):
            preview = chunk["chunk_text"][:50].replace("\n", " ")
            logger.info(
                f"Embedding chunk {i}/{total} (article_id={chunk['article_id']}): {preview!r}"
            )

        texts = [c["chunk_text"] for c in new_chunks]
        dense_vecs = encode_passage(texts)
        sparse_vecs = encode_sparse(texts)
        upsert_chunks(new_chunks, dense_vecs, sparse_vecs)

        for chunk in new_chunks:
            try:
                _store_in_postgres(chunk)
            except Exception as e:
                logger.error(f"Failed to store chunk {chunk.get('chunk_id')} in PostgreSQL: {e}")

    return {"processed": len(chunks), "indexed": len(new_chunks), "skipped": skipped}


def run(chunks_file: Optional[str] = None) -> dict[str, int]:
    """Embed and store all (or one) chunk file(s) into Qdrant and PostgreSQL.

    Args:
        chunks_file: Optional specific chunks JSON file to process. Defaults to
            processing every file in data/chunks/.

    Returns:
        Summary dict with counts of processed, indexed, and skipped chunks.
    """
    postgres.init_schema()
    init_collection()

    files = (
        [chunks_file]
        if chunks_file
        else [os.path.join(DATA_CHUNKS_DIR, f) for f in os.listdir(DATA_CHUNKS_DIR) if f.endswith(".json")]
    )

    totals = {"processed": 0, "indexed": 0, "skipped": 0}

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read chunks file {path}: {e}")
            continue

        try:
            result = embed_and_store(chunks)
        except Exception as e:
            logger.error(f"Failed to embed chunks file {path}: {e}")
            continue

        for key in totals:
            totals[key] += result[key]

    logger.info(
        f"Embedding complete: {totals['processed']} processed, "
        f"{totals['indexed']} indexed, {totals['skipped']} already indexed"
    )
    return totals


if __name__ == "__main__":
    run()
