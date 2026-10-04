"""Hybrid (dense + BM25) search + cross-encoder reranking for the search API.

Reuses vectorization/embedder.py's model singletons and encode functions
directly, rather than loading a second copy of the same models — the
dense/sparse models here must stay byte-for-byte the same ones used by the
indexing pipeline (vectorization/qdrant_store.py, vectorization/embedder.py),
or query-side vectors won't be compatible with what was indexed.

hybrid_search() over-fetches (top_k * 4) RRF-fused candidates from Qdrant,
then reranks them with a cross-encoder (bge-reranker-v2-m3) that scores each
(query, chunk_text) pair directly — RRF's rank-based fusion is a good coarse
filter but doesn't itself guarantee the most relevant chunk ends up first;
the cross-encoder re-scores the candidate set with a model that sees the
query and chunk together, rather than as two independently-embedded vectors.
"""
import hashlib
from typing import Any

import torch
from loguru import logger
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector
from sentence_transformers import CrossEncoder

from config import QDRANT_COLLECTION, RERANKER_MODEL_NAME, RERANKER_TOP_K, RETRIEVAL_TOP_K
from vectorization.embedder import encode_query, encode_sparse, get_dense_model, get_sparse_model
from vectorization.qdrant_store import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, get_client

__all__ = ["get_dense_model", "get_sparse_model", "get_reranker", "encode_query", "encode_sparse", "hybrid_search"]

_FETCH_MULTIPLIER = 4

_reranker: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    """Return a lazily-initialized, module-level cross-encoder reranker."""
    global _reranker
    if _reranker is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _reranker = CrossEncoder(RERANKER_MODEL_NAME, device=device, max_length=512)
    return _reranker


def _hash_article_id(article_id: Any) -> str:
    """MD5-hash an article id so the raw UUID is never exposed to clients.

    Args:
        article_id: The article's UUID (or string form) from the chunk payload.

    Returns:
        Hex-encoded MD5 digest of the article id.
    """
    return hashlib.md5(str(article_id).encode("utf-8")).hexdigest()


def rerank(query: str, results: list[dict[str, Any]], top_k: int = RERANKER_TOP_K) -> list[dict[str, Any]]:
    """Score each (query, chunk_text) pair with the cross-encoder and keep the top_k.

    Args:
        query: The user's natural-language search query.
        results: Candidate result dicts from hybrid_search's RRF fusion step.
        top_k: Number of top-scoring results to keep.

    Returns:
        The top_k results, sorted by rerank score descending. Empty input
        returns empty output without loading the reranker model.
    """
    if not results:
        return results

    reranker = get_reranker()
    pairs = [[query, r["chunk_text"]] for r in results]
    scores = reranker.predict(pairs)

    scored = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]


def hybrid_search(query: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict[str, Any]]:
    """Hybrid dense + BM25 search, RRF-fused, then cross-encoder reranked.

    Args:
        query: The user's natural-language search query.
        top_k: Number of results to return after reranking.

    Returns:
        List of result dicts with title, url, keyword, language, chunk_text,
        chunk_index, and article_id (MD5-hashed), ordered by rerank score.
    """
    client = get_client()
    dense_query = encode_query(query)
    sparse_query = encode_sparse([query])[0]

    # Over-fetch RRF candidates so the reranker has a wider pool to pick
    # top_k good matches from, rather than reranking (and being limited to)
    # only the fusion's own top_k.
    fetch_k = top_k * _FETCH_MULTIPLIER

    dense_prefetch = Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=fetch_k)
    sparse_prefetch = Prefetch(
        query=SparseVector(indices=sparse_query.indices.tolist(), values=sparse_query.values.tolist()),
        using=SPARSE_VECTOR_NAME,
        limit=fetch_k,
    )

    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        prefetch=[dense_prefetch, sparse_prefetch],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=fetch_k,
        with_payload=True,
    )

    if not results.points:
        logger.info(f"No Qdrant hits for query: {query!r}")
        return []

    raw_results = [
        {
            "title": point.payload.get("title"),
            "url": point.payload.get("url"),
            "keyword": point.payload.get("keyword"),
            # PDF chunks have no "language" field; default to Indonesian.
            "language": point.payload.get("language") or "id",
            # PDF chunks (pdf_ingestor.py) store their text under "content", not "chunk_text".
            "chunk_text": point.payload.get("chunk_text") or point.payload.get("content"),
            # PDF chunks store the index as "chunk_idx". Not `or`: index 0 is falsy.
            "chunk_index": point.payload["chunk_index"] if "chunk_index" in point.payload else point.payload.get("chunk_idx"),
            "article_id": _hash_article_id(point.payload.get("article_id")),
        }
        for point in results.points
    ]

    return rerank(query, raw_results, top_k=top_k)
