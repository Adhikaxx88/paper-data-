# Embedder

`pipeline/embedder.py`, backed by `vectorization/embedder.py` and
`vectorization/qdrant_store.py`.

## Embedding models

Two models are loaded **natively, in-process** — no separate embedding
server or container:

- **Dense**: `BAAI/bge-large-en-v1.5` (1024 dimensions) via
  [sentence-transformers](https://www.sbert.net/), for semantic similarity.
- **Sparse**: `Qdrant/bm25` (`SPARSE_MODEL_NAME`) via
  [fastembed](https://github.com/qdrant/fastembed), for exact keyword
  matching.

Both are lazily initialized once per process as module-level singletons in
`vectorization/embedder.py`, so repeated calls reuse the loaded model
instead of reloading weights.

### Device detection

`vectorization/embedder.py` picks its device once at import time:

```python
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
```

If a CUDA GPU is visible to the process (the common case when running the
pipeline/backend natively on the host rather than in Docker, where GPU
passthrough would otherwise need extra configuration), the dense model runs
on it; otherwise it falls back to CPU automatically. No config flag is
needed — swap hardware and the next run picks it up.

### BGE asymmetric embedding

BGE is an *asymmetric* model: it was trained to embed queries and passages
differently for best retrieval quality.

- **Passages** (`encode_passage`) are embedded as-is — no prefix.
- **Queries** (`encode_query`) are embedded with `BGE_QUERY_INSTRUCTION`
  (`config.py`, default `"Represent this sentence for searching relevant
  passages: "`) prepended.

Getting this backwards — prefixing passages, or leaving queries unprefixed —
measurably hurts retrieval quality, since the model was never trained on
those input shapes. `pipeline/embedder.py` always calls `encode_passage`;
[the retriever](../rag/retriever.md) always calls `encode_query`.

## How chunks flow into Qdrant and PostgreSQL

For each chunk file in `data/chunks/*.json`, `embed_and_store()`:

1. Ensures the Qdrant collection exists (`vectorization.qdrant_store.init_collection`),
   configured with two named vectors: `dense` (BGE, `EMBED_DIM`-dimensional,
   cosine) and `bm25` (sparse).
2. Filters out chunks whose `chunk_id` is already a point in Qdrant
   (`point_exists`) — this is the idempotency check.
3. Batch-embeds the remaining chunks' `chunk_text`: `encode_passage` for the
   dense vectors, `encode_sparse` for the BM25 vectors.
4. Upserts each chunk into Qdrant (in batches of 64) with **both** vectors
   and a payload carrying `chunk_id`, `article_id`, `title`, `url`, `date`,
   `source`, `category`, `chunk_index`, and — unlike the previous
   OpenAI/infinity-emb setup — **`chunk_text` itself**. Storing the text in
   the payload means retrieval never needs a PostgreSQL round-trip; see
   [Architecture → Why PostgreSQL + Qdrant together](../architecture.md#why-postgresql--qdrant-together).
5. Also upserts the parent article and chunk text into PostgreSQL, for chat
   history/tooling use — not for retrieval.

## Why hybrid (dense + sparse) instead of dense-only

Dense embeddings are good at semantic/contextual similarity but can miss or
dilute exact matches on things like company names, regulation numbers, or
dates — a query for "OJK POJK 10/2022" and a passage discussing "the new
lending regulation" might embed close together even when the user wanted the
literal POJK number. BM25 sparse search is the opposite: strong on exact
keyword/entity/number matches, weak on paraphrase and synonymy. Combining
both (see [the retriever](../rag/retriever.md)) captures more relevant
passages than either alone.

## Idempotency

Because `chunk_id` is deterministic (derived from the article URL and chunk
index), re-running the embedder on the same chunks is safe: chunks already
present in Qdrant are skipped without re-calling the embedding models, so no
duplicate work and no duplicate vectors.

## How to re-index from scratch

```bash
# Drop and recreate the Qdrant collection at the current EMBED_DIM
python -c "from vectorization.qdrant_store import recreate_collection; recreate_collection()"

# Re-run chunking + embedding from the existing clean/chunk JSON files
python run_pipeline.py --step embed
```
