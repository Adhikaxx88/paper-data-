"""Qdrant vector store access layer for the news_chunks collection."""
import uuid
from typing import Any, Optional

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from config import EMBED_DIM, QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """Return a lazily-initialized, module-level Qdrant client.

    Returns:
        A connected QdrantClient instance.
    """
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    return _client


def init_collection() -> None:
    """Create the news_chunks collection if it does not already exist."""
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        logger.info(f"Qdrant collection '{QDRANT_COLLECTION}' already exists")
        return
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qmodels.VectorParams(size=EMBED_DIM, distance=qmodels.Distance.COSINE),
    )
    logger.info(f"Created Qdrant collection '{QDRANT_COLLECTION}' (dim={EMBED_DIM})")


def recreate_collection() -> None:
    """Drop and recreate the news_chunks collection using the current EMBED_DIM.

    Run this manually when changing embedding models (e.g. switching from
    OpenAI's 1536-dim text-embedding-3-small to BGE's 1024-dim
    bge-large-en-v1.5) to avoid a vector dimension mismatch. All previously
    indexed vectors are lost — chunks must be re-embedded afterward via
    `pipeline/embedder.py`. PostgreSQL data (articles, chunks text) is
    unaffected and does not need to be re-scraped or re-chunked.
    """
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        client.delete_collection(QDRANT_COLLECTION)
        logger.info(f"Deleted Qdrant collection '{QDRANT_COLLECTION}'")
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qmodels.VectorParams(size=EMBED_DIM, distance=qmodels.Distance.COSINE),
    )
    logger.info(f"Recreated Qdrant collection '{QDRANT_COLLECTION}' (dim={EMBED_DIM})")


def point_exists(chunk_id: uuid.UUID) -> bool:
    """Check whether a vector for the given chunk_id is already indexed.

    Args:
        chunk_id: The chunk's UUID, used as the Qdrant point id.

    Returns:
        True if a point with this id already exists.
    """
    client = get_client()
    result = client.retrieve(collection_name=QDRANT_COLLECTION, ids=[str(chunk_id)])
    return len(result) > 0


def upsert_point(chunk_id: uuid.UUID, vector: list[float], payload: dict[str, Any]) -> None:
    """Upsert a single embedding vector with its payload.

    Args:
        chunk_id: The chunk's UUID, used as the Qdrant point id.
        vector: The embedding vector.
        payload: Metadata stored alongside the vector (chunk_id, article_id, title, source, date, category).
    """
    client = get_client()
    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[qmodels.PointStruct(id=str(chunk_id), vector=vector, payload=payload)],
    )


def search(query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
    """Run a cosine similarity search against the news_chunks collection.

    Args:
        query_vector: The embedded user query.
        top_k: Number of nearest neighbors to return.

    Returns:
        List of dicts with chunk_id, score, and payload.
    """
    client = get_client()
    results = client.search(collection_name=QDRANT_COLLECTION, query_vector=query_vector, limit=top_k)
    return [{"chunk_id": r.id, "score": r.score, "payload": r.payload} for r in results]
