"""Retrieve relevant news chunks for a user query via hybrid (dense + BM25) Qdrant search."""
import hashlib
from typing import Any, Optional

from loguru import logger
from qdrant_client.models import Filter, FieldCondition, Fusion, FusionQuery, MatchValue, Prefetch, SparseVector

from config import QDRANT_COLLECTION, RETRIEVAL_TOP_K
from vectorization.embedder import encode_query, encode_sparse
from vectorization.qdrant_store import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, get_client


def _hash_article_id(article_id: Any) -> str:
    """MD5-hash an article id so the raw UUID is never exposed to clients.

    Args:
        article_id: The article's UUID (or string form) from the chunk payload.

    Returns:
        Hex-encoded MD5 digest of the article id.
    """
    return hashlib.md5(str(article_id).encode("utf-8")).hexdigest()


def retrieve(query: str, top_k: int = RETRIEVAL_TOP_K, category: Optional[str] = None) -> list[dict[str, Any]]:
    """Hybrid search: dense (BGE) + sparse (BM25) prefetch fused via RRF.

    chunk_text and article metadata are read directly from the Qdrant
    payload, so no PostgreSQL lookup is needed at retrieval time.

    Args:
        query: The user's natural-language question.
        top_k: Number of results to return after fusion.
        category: Optional exact-match filter on the article's category.

    Returns:
        List of dicts with chunk_text, title, source, date, category, url, score,
        and article_id (MD5-hashed), ordered by descending fused score.
    """
    client = get_client()
    dense_query = encode_query(query)
    sparse_query = encode_sparse([query])[0]

    query_filter = None
    if category:
        query_filter = Filter(must=[FieldCondition(key="category", match=MatchValue(value=category))])

    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        prefetch=[
            Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=top_k * 2),
            Prefetch(
                query=SparseVector(
                    indices=sparse_query.indices.tolist(),
                    values=sparse_query.values.tolist(),
                ),
                using=SPARSE_VECTOR_NAME,
                limit=top_k * 2,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    if not results.points:
        logger.info(f"No Qdrant hits for query: {query!r}")
        return []

    return [
        {
            # PDF chunks (pdf_ingestor.py) store their text under "content", not "chunk_text".
            "chunk_text": point.payload.get("chunk_text") or point.payload.get("content"),
            "title": point.payload.get("title"),
            "source": point.payload.get("source"),
            "date": point.payload.get("date"),
            "category": point.payload.get("category"),
            "url": point.payload.get("url"),
            "score": point.score,
            "article_id": _hash_article_id(point.payload.get("article_id")),
        }
        for point in results.points
    ]


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "berita fintech terbaru"
    for r in retrieve(q):
        print(f"[{r['score']:.3f}] {r['title']} ({r['source']}, {r['date']})")
