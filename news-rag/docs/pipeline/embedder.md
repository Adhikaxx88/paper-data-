# Embedder

`pipeline/embedder.py`

## Embedding model

By default, embeds with **`BAAI/bge-large-en-v1.5`** (1024 dimensions),
served locally by [infinity-emb](https://github.com/michaelfeil/infinity)
(the `infinity` service in `docker-compose.yml`). infinity-emb exposes an
OpenAI-compatible `/embeddings` endpoint, so `pipeline/embedder.py` talks to
it with the standard `openai` SDK, just pointed at `INFINITY_URL`
(`config.py`) instead of `api.openai.com` — no API key or external network
call required. Swap `EMBED_MODEL` / `EMBED_DIM` in `.env` to use a different
model or point back at OpenAI's `text-embedding-3-small` (1536-dim); see the
[dimension-mismatch warning](../setup.md#switching-embedding-models-openai-bge-or-bge-a-different-model)
if you do.

BGE models expect an instruction prefix on the text being embedded for best
retrieval quality, and the prefix differs for indexed passages vs. search
queries. The embedder prepends `PASSAGE_PREFIX` ("Represent this sentence
for searching relevant passages: ") to `chunk_text` before embedding; the
[retriever](../rag/retriever.md) prepends a different, query-specific prefix
to the user's question.

## How chunks flow into Qdrant and PostgreSQL

For each chunk in `data/chunks/*.json`:

1. Check if the chunk is already stored (`db.postgres.chunk_exists`) **and**
   already indexed in Qdrant (`db.qdrant_client.point_exists`). If both are
   true, skip it.
2. Upsert the parent article's metadata into PostgreSQL `articles`
   (`source`, `title`, `date`, `url`, `category`), keyed by the deterministic
   `article_id` from the [chunker](chunker.md).
3. Insert the chunk's `chunk_text` into PostgreSQL `chunks`.
4. Call the embeddings API (infinity-emb by default) on the prefixed
   `chunk_text` to get an `EMBED_DIM`-dimensional vector.
5. Upsert the vector into the Qdrant `news_chunks` collection, with the
   point id set to `chunk_id` and payload set to `chunk_id`, `article_id`,
   `title`, `source`, `date`, `category` — **not** `chunk_text`, which stays
   in PostgreSQL only.

## Idempotency

Because `chunk_id` is deterministic (derived from the article URL and chunk
index), re-running the embedder on the same chunks is safe: chunks already
present in both PostgreSQL and Qdrant are skipped without re-calling the
embedding API, so no duplicate work and no duplicate vectors.

## How to re-index from scratch

```bash
# Drop and recreate the Qdrant collection at the current EMBED_DIM
python -c "from db.qdrant_client import recreate_collection; recreate_collection()"

# Truncate the PostgreSQL tables that hold indexed data
psql $POSTGRES_URL -c "TRUNCATE chunks, articles CASCADE;"

# Re-run chunking + embedding from the existing clean/chunk JSON files
python run_pipeline.py --step embed
```
