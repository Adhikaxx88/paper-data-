# Qdrant

`db/qdrant_client.py`

Qdrant stores only what's needed for fast vector similarity search. See
[Architecture](../architecture.md) for why the text itself lives in
PostgreSQL instead.

## Collection config

| Setting | Value |
|---|---|
| Collection name | `news_chunks` |
| Vector size | `EMBED_DIM` in `config.py`, default `1024` (matches `BAAI/bge-large-en-v1.5`) |
| Distance metric | Cosine |
| Point id | `chunk_id` (as a string UUID) |

Created by `db.qdrant_client.init_collection()`, which is a no-op if the
collection already exists — safe to call on every pipeline run. If you
change `EMBED_MODEL`/`EMBED_DIM` after a collection already exists, use
`db.qdrant_client.recreate_collection()` instead — it drops and recreates
the collection at the new dimension. See the
[dimension-mismatch warning](../setup.md#switching-embedding-models-openai-bge-or-bge-a-different-model)
in Setup.

## What's stored in payload vs. PostgreSQL

| Field | Qdrant payload | PostgreSQL |
|---|---|---|
| `chunk_id` | ✅ | ✅ (primary key) |
| `article_id` | ✅ | ✅ |
| `title` | ✅ | ✅ |
| `source` | ✅ | ✅ |
| `date` | ✅ | ✅ |
| `category` | ✅ | ✅ |
| `chunk_text` | ❌ | ✅ (only here) |

Qdrant's payload carries just enough metadata to identify and describe a
match; the actual chunk text is always fetched from PostgreSQL by `chunk_id`
after the vector search returns.

## How similarity search works

1. The user's query is embedded with the same model used for indexing
   (`EMBED_MODEL`, default `BAAI/bge-large-en-v1.5`), via
   `pipeline.embedder.embed_text`.
2. `db.qdrant_client.search(query_vector, top_k)` runs a cosine-similarity
   nearest-neighbor search against the `news_chunks` collection.
3. Each result returns `chunk_id`, a similarity `score`, and the payload.
4. The `chunk_id`s are passed to PostgreSQL to fetch the corresponding
   `chunk_text` and article metadata, and results are re-attached to their
   scores.

See [Retriever](../rag/retriever.md) for the full step-by-step flow.
