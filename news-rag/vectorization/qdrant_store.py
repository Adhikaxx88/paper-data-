"""Qdrant vector store access layer for the news_chunks collection.

The collection carries two named vectors per point — a dense BGE vector for
semantic search and a sparse BM25 vector for keyword search — combined at
query time via RRF fusion (see rag/retriever.py). chunk_text and article
metadata are stored directly in the Qdrant payload so retrieval never needs
a PostgreSQL round-trip.
"""
import uuid
from typing import Any, Optional

from fastembed import SparseEmbedding
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from config import EMBED_DIM, QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"

_UPSERT_BATCH_SIZE = 64

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
    """Create the news_chunks collection (dense + sparse vectors) if missing."""
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        logger.info(f"Qdrant collection '{QDRANT_COLLECTION}' already exists")
        return
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(index=SparseIndexParams(on_disk=False)),
        },
    )
    logger.info(f"Created Qdrant collection '{QDRANT_COLLECTION}' (dense={EMBED_DIM}, sparse=bm25)")


def recreate_collection() -> None:
    """Drop and recreate the news_chunks collection using the current EMBED_DIM.

    Run this manually when changing the dense embedding model to avoid a
    vector dimension mismatch. All previously indexed vectors are lost —
    chunks must be re-embedded afterward via `pipeline/embedder.py`.
    """
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        client.delete_collection(QDRANT_COLLECTION)
        logger.info(f"Deleted Qdrant collection '{QDRANT_COLLECTION}'")
    init_collection()


def point_exists(chunk_id: uuid.UUID) -> bool:
    """Check whether a point for the given chunk_id is already indexed.

    Args:
        chunk_id: The chunk's UUID, used as the Qdrant point id.

    Returns:
        True if a point with this id already exists.
    """
    client = get_client()
    result = client.retrieve(collection_name=QDRANT_COLLECTION, ids=[str(chunk_id)])
    return len(result) > 0


def _to_qdrant_sparse(sparse: SparseEmbedding) -> SparseVector:
    return SparseVector(indices=sparse.indices.tolist(), values=sparse.values.tolist())


def upsert_chunks(
    chunks: list[dict[str, Any]],
    dense_vecs: list[list[float]],
    sparse_vecs: list[SparseEmbedding],
) -> None:
    """Upsert chunks with their dense + sparse vectors and full payload, in batches.

    Args:
        chunks: Chunk dicts as produced by pipeline.chunker (chunk_id, article_id,
            source, title, date, category, sub_area, keyword, url,
            chunk_index, chunk_text).
        dense_vecs: One dense vector per chunk, same order as chunks.
        sparse_vecs: One sparse embedding per chunk, same order as chunks.
    """
    client = get_client()
    points = [
        PointStruct(
            id=chunk["chunk_id"],
            vector={
                DENSE_VECTOR_NAME: dense_vec,
                SPARSE_VECTOR_NAME: _to_qdrant_sparse(sparse_vec),
            },
            payload={
                "chunk_id": chunk["chunk_id"],
                "article_id": chunk["article_id"],
                "title": chunk["title"],
                "url": chunk["url"],
                "date": chunk["date"],
                "source": chunk["source"],
                "category": chunk["category"],
                "sub_area": chunk.get("sub_area"),
                "keyword": chunk.get("keyword"),
                "language": chunk.get("language", "en"),
                "chunk_index": chunk["chunk_index"],
                "chunk_text": chunk["chunk_text"],
            },
        )
        for chunk, dense_vec, sparse_vec in zip(chunks, dense_vecs, sparse_vecs)
    ]

    for i in range(0, len(points), _UPSERT_BATCH_SIZE):
        batch = points[i : i + _UPSERT_BATCH_SIZE]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
