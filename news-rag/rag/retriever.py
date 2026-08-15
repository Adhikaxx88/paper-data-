"""Retrieve relevant news chunks for a user query via Qdrant + PostgreSQL."""
import uuid
from typing import Any

from loguru import logger

from config import RETRIEVAL_TOP_K
from db import postgres, qdrant_client
from pipeline.embedder import embed_text

# BGE models expect a different instruction prefix for search queries than
# for indexed passages (see pipeline/embedder.py's PASSAGE_PREFIX).
QUERY_PREFIX = "Represent this question for searching relevant passages: "


def retrieve(query: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict[str, Any]]:
    """Embed a query, search Qdrant, and fetch matching chunk text from PostgreSQL.

    Args:
        query: The user's natural-language question.
        top_k: Number of nearest chunks to retrieve.

    Returns:
        List of dicts with chunk_text, title, source, date, category, url, and score,
        ordered by descending similarity score.
    """
    query_vector = embed_text(QUERY_PREFIX + query)
    hits = qdrant_client.search(query_vector, top_k)
    if not hits:
        logger.info(f"No Qdrant hits for query: {query!r}")
        return []

    scores_by_chunk_id = {uuid.UUID(hit["chunk_id"]): hit["score"] for hit in hits}
    chunk_ids = list(scores_by_chunk_id.keys())
    rows = postgres.get_chunks_by_ids(chunk_ids)

    results = [
        {
            "chunk_text": row["chunk_text"],
            "title": row["title"],
            "source": row["source"],
            "date": row["date"],
            "category": row["category"],
            "url": row["url"],
            "score": scores_by_chunk_id.get(row["chunk_id"], 0.0),
        }
        for row in rows
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "berita fintech terbaru"
    for r in retrieve(q):
        print(f"[{r['score']:.3f}] {r['title']} ({r['source']}, {r['date']})")
