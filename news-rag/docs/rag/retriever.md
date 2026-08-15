# Retriever

`rag/retriever.py`

## Step-by-step: query → embed → search → fetch

1. **Embed the query.** The user's question is embedded with the exact same
   model used to embed chunks at indexing time
   (`text-embedding-3-small`, via `pipeline.embedder.embed_text`). Using a
   different model here would make the query vector incomparable to the
   stored chunk vectors.
2. **Search Qdrant.** `db.qdrant_client.search(query_vector, top_k)` runs a
   cosine-similarity nearest-neighbor search over the `news_chunks`
   collection and returns the top-K `chunk_id`s with their scores.
3. **Fetch from PostgreSQL.** The returned `chunk_id`s are passed to
   `db.postgres.get_chunks_by_ids`, which joins `chunks` and `articles` to
   return `chunk_text`, `title`, `source`, `date`, `category`, and `url`.
4. **Re-attach scores and sort.** Because PostgreSQL doesn't preserve Qdrant's
   ranking, results are re-sorted by the original similarity score, highest
   first, before being returned.

The function returns a list of dicts:

```python
{
    "chunk_text": str,
    "title": str,
    "source": str,
    "date": str,
    "category": str,
    "url": str,
    "score": float,
}
```

## What K=5 means and how to tune it

`K` (`RETRIEVAL_TOP_K` in `config.py`, default `5`) is the number of chunks
retrieved per question. Each retrieved chunk becomes one numbered source in
the prompt sent to the [generator](generator.md).

- **Lower K** (e.g. 3) → tighter, more focused context, less risk of
  irrelevant chunks diluting the answer, but higher risk of missing a
  relevant fact that didn't quite make the cut.
- **Higher K** (e.g. 8–10) → more coverage for broad questions, at the cost
  of a longer prompt (more tokens, higher latency/cost) and more noise for
  the LLM to filter out.

Tune it by changing `RETRIEVAL_TOP_K` in `config.py`, or by passing
`top_k=` directly to `retrieve()`.
