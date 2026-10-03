# Retrieval: Hybrid Search

Implemented by `hybrid_search()` in `backend/retrieval/searcher.py`, called
by `backend/routers/search.py` only after every input guardrail check
passes. `searcher.py` doesn't load its own copy of the embedding models or
re-implement encoding — it imports `get_dense_model`, `get_sparse_model`,
`encode_query`, and `encode_sparse` directly from `vectorization/embedder.py`
and re-exports them, so the indexing pipeline and the query path share the
exact same loaded model instances (not just the same model *names*) — this
avoids holding two copies of e5-large + BM25 in memory, and guarantees
query-side vectors stay compatible with what was indexed.

## Dense vector: `intfloat/multilingual-e5-large`

A multilingual, **asymmetric** embedding model (`config.DENSE_MODEL_NAME`,
1024-dim, `config.EMBED_DIM`): the text you're embedding needs a different
prefix depending on whether it's a search query or a document/passage
being indexed.

- **Indexing** (`vectorization/embedder.py:encode_passage`): prepends
  `"passage: "` to each chunk before encoding.
- **Querying** (`vectorization/embedder.py:encode_query`, imported into
  `backend/retrieval/searcher.py`): prepends `config.BGE_QUERY_INSTRUCTION`
  (`"query: "`) to the query text before encoding.

Mixing these up (no prefix on either side, or the same prefix on both)
measurably hurts retrieval quality — e5 was trained specifically to expect
this asymmetry. Both vectors are L2-normalized (`normalize_embeddings=True`)
for cosine similarity.

```python
# vectorization/embedder.py
def encode_query(query: str) -> list[float]:
    prefixed = BGE_QUERY_INSTRUCTION + query  # "query: " + query
    vector = get_dense_model().encode(prefixed, normalize_embeddings=True)
    return vector.tolist()
```

## Sparse vector: BM25 (fastembed)

`config.SPARSE_MODEL_NAME` (`Qdrant/bm25`, loaded via fastembed's
`SparseTextEmbedding`) — a classic lexical/keyword scorer. No prefix, no
asymmetry; the same `encode_sparse()` call is used for both indexing and
querying. Dense search captures semantic similarity; BM25 catches exact
keyword, number, and named-entity matches (e.g. a specific law, agency
name, or statistic) that dense embeddings can dilute or miss entirely.

## Fusion: RRF in Qdrant

A single `client.query_points()` call does both retrieval and fusion
server-side:

```python
fetch_k = top_k * 4  # over-fetch so the reranker has a real pool to work with

results = client.query_points(
    collection_name=QDRANT_COLLECTION,
    prefetch=[
        Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=fetch_k),
        Prefetch(query=SparseVector(...), using=SPARSE_VECTOR_NAME, limit=fetch_k),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=fetch_k,
    with_payload=True,
)
```

Each prefetch independently retrieves `fetch_k` (= `top_k * 4`) candidates by
its own metric (cosine for dense, BM25 score for sparse); Qdrant's built-in
**Reciprocal Rank Fusion** then merges the two ranked lists into one
combined ranking based on each candidate's *rank* in each list (not its raw
score, which isn't comparable across dense/sparse), and the top `fetch_k` of
that fused ranking is returned — **not yet `top_k`**; the reranker (below)
is what narrows `fetch_k` candidates down to the final `top_k`.
`with_payload=True` means the full chunk payload — `chunk_text` included —
comes back on the same call, so `hybrid_search()` never round-trips to
PostgreSQL.

## Reranking: cross-encoder (`bge-reranker-v2-m3`)

RRF fusion is a good coarse filter, but it ranks by each candidate's
*position* within two independently-computed lists (dense cosine similarity,
BM25 score) — it never actually looks at the query and a chunk *together*,
so the most semantically relevant chunk isn't guaranteed to end up ranked
first. `rerank()` (`backend/retrieval/searcher.py`) fixes this with a
**cross-encoder**: a model that takes `(query, chunk_text)` as a single
joint input and outputs one relevance score per pair, directly.

**Model:** `config.RERANKER_MODEL_NAME` (`BAAI/bge-reranker-v2-m3`) — like
the dense embedder, it's multilingual, so it scores Indonesian and English
`(query, chunk)` pairs natively without needing translation or a
language-specific model swap.

**Flow** (`hybrid_search()` → `rerank()`):

```python
pairs = [[query, r["chunk_text"]] for r in results]   # fetch_k pairs
scores = reranker.predict(pairs)                       # one score per pair
scored = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
return [r for _, r in scored[:top_k]]                  # config.RERANKER_TOP_K by default
```

`hybrid_search()` calls `rerank(query, raw_results, top_k=top_k)` — the
*same* `top_k` the caller passed to `hybrid_search()` (ultimately
`SearchRequest.top_k` / `config.RETRIEVAL_TOP_K`), not a second independent
value; `config.RERANKER_TOP_K` only supplies `rerank()`'s own default when
it's called without an explicit `top_k` (it isn't, from `hybrid_search()`).

**Model loading:** `get_reranker()` lazily loads `CrossEncoder` once per
process (module-level singleton, same pattern as
`vectorization/embedder.py`'s dense/sparse models), on **CUDA if available,
else CPU** (`torch.cuda.is_available()`), with `max_length=512` tokens per
pair. An empty candidate list short-circuits `rerank()` before touching the
model at all, so a query with zero Qdrant hits never triggers a reranker
load.

## No language filter — why results mix `id` and `en`

`hybrid_search()` passes no `query_filter` on `language` (unlike
`rag/retriever.py`'s optional `category` filter, which it also doesn't use
here). This is deliberate: `multilingual-e5-large` embeds Indonesian and
English text into the *same* semantic vector space, so a query in either
language can — and often should — surface relevant chunks from articles
written in the other language. A search for `"dampak bullying pada remaja"`
can return both Indonesian-language sources and English-language sources
discussing the same phenomenon, ranked purely by relevance, not by matching
the query's language. `detected_lang` (from the `language_detect`
guardrail) only controls which language `generate_answer()` writes its
answer in — it never filters which chunks retrieval considers.

## Result shape and article-id hashing

Right after fusion, each of the `fetch_k` Qdrant points' payload is
projected down to exactly the fields the API needs, with `article_id`
MD5-hashed so the raw PostgreSQL UUID is never exposed to the client:

```python
{
    "title": point.payload.get("title"),
    "url": point.payload.get("url"),
    "keyword": point.payload.get("keyword"),
    "language": point.payload.get("language"),
    "chunk_text": point.payload.get("chunk_text"),
    "chunk_index": point.payload.get("chunk_index"),
    "article_id": hashlib.md5(str(point.payload.get("article_id")).encode()).hexdigest(),
}
```

This `fetch_k`-long list is `rerank()`'s input; `hybrid_search()` returns
only what `rerank()` keeps — the top `top_k` after cross-encoder scoring,
same dict shape. That's what `protect_output()` (see
[guardrails.md#output-protection](guardrails.md#output-protection)) then
truncates/redacts/allowlists before it reaches the client or
`generate_answer()`.
