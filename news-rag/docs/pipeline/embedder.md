# Embedder

`pipeline/embedder.py`

## Embedding model

Uses OpenAI's **`text-embedding-3-small`** (1536 dimensions). It was chosen
because it offers strong retrieval quality at a fraction of the cost and
latency of larger embedding models, which matters for a pipeline that
re-embeds every chunk of every scraped article.

## How chunks flow into Qdrant and PostgreSQL

For each chunk in `data/chunks/*.json`:

1. Check if the chunk is already stored (`db.postgres.chunk_exists`) **and**
   already indexed in Qdrant (`db.qdrant_client.point_exists`). If both are
   true, skip it.
2. Upsert the parent article's metadata into PostgreSQL `articles`
   (`source`, `title`, `date`, `url`, `category`), keyed by the deterministic
   `article_id` from the [chunker](chunker.md).
3. Insert the chunk's `chunk_text` into PostgreSQL `chunks`.
4. Call the OpenAI embeddings API on `chunk_text` to get a 1536-dim vector.
5. Upsert the vector into the Qdrant `news_chunks` collection, with the
   point id set to `chunk_id` and payload set to `chunk_id`, `article_id`,
   `title`, `source`, `date`, `category` — **not** `chunk_text`, which stays
   in PostgreSQL only.

## Idempotency

Because `chunk_id` is deterministic (derived from the article URL and chunk
index), re-running the embedder on the same chunks is safe: chunks already
present in both PostgreSQL and Qdrant are skipped without calling the OpenAI
API again, so no duplicate spend and no duplicate vectors.

## How to re-index from scratch

```bash
# Drop and recreate the Qdrant collection
python -c "from db.qdrant_client import get_client; from config import QDRANT_COLLECTION; get_client().delete_collection(QDRANT_COLLECTION)"

# Truncate the PostgreSQL tables that hold indexed data
psql $POSTGRES_URL -c "TRUNCATE chunks, articles CASCADE;"

# Re-run chunking + embedding from the existing clean/chunk JSON files
python run_pipeline.py --step embed
```
