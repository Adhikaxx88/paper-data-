# Architecture

The system has four layers: a **batch pipeline** that builds the knowledge
base, an **online API** (FastAPI) exposing two independent chat backends, a
**React chat UI** that talks to the simpler of the two, and an **evaluation
pipeline** that scores the chatbot against a golden Q&A dataset.

> **Which API does the frontend actually use?** `backend/main.py` mounts
> two unrelated chat pipelines side by side: the plain `/api/session` +
> `/api/chat` pipeline (backed by `rag/pipeline.py`) and the guardrailed
> `/api/search` pipeline (backed by `backend/routers/search.py` and the
> `backend/guardrails|retrieval|generation` packages, diagrammed below).
> **The shipped React frontend (`frontend/src/api/chat.ts`) talks only to
> `/api/session`/`/api/chat`** — no guardrails, no reranker, no hybrid-search
> fusion. The guardrailed `/api/search` pipeline is fully implemented and
> still works (call it directly, e.g. via `curl` or `GET /docs`), it's just
> not wired into the current UI. See [Two chat backends](#two-chat-backends-apichat-vs-apisearch)
> below for why both exist and what each one gives you.

## End-to-end data flow

```
┌────────────────────────── BATCH PIPELINE (offline, run_pipeline.py) ───────────────────────────┐
│                                                                                                   │
│  Google News RSS --scrape--> raw_articles --clean--> clean_articles --chunk--> chunks            │
│   (pipeline/scraper.py)  (pipeline/cleaner.py)  (pipeline/chunker.py)              │              │
│                                                            │                        ▼              │
│                                                            │                  pipeline/embedder.py  │
│                                                            │                (dense e5-large +       │
│                                                            ▼                 sparse BM25)           │
│                                                    pipeline/pdf_exporter.py         │               │
│                                                            │                        ▼               │
│                                                    data/pdf/*.pdf              Qdrant collection    │
│                                                            │                  "data-paper-child"     │
│                                                   (dosen review →                                   │
│                                                 data/classified-2/)                                 │
│                                                            │                                        │
│                                                            ▼                                        │
│                                                    sync_reviewed.py                                 │
│                                              (deletes rejected articles                             │
│                                               from raw_articles/clean_articles)                     │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────── ONLINE API — guardrailed /api/search pipeline (not wired to any UI) ────────────────┐
│                                                                                                   │
│  API client ──POST /api/search──▶ FastAPI app (backend/main.py)                                 │
│                                              │                                                    │
│                                              ▼                                                    │
│                              backend/routers/search.py: search()                                  │
│                                              │                                                    │
│   1. get_or_create_session(session_id)      │  backend/session.py — in-memory, 1h TTL             │
│                                              ▼                                                    │
│   2. run_input_guardrails(query, history)   │  backend/guardrails/input.py                        │
│      encoding → regex → injection →         │  stops at first FAILURE                             │
│      multiturn → scope → language_detect    │                                                     │
│                                              │                                                     │
│              FAIL ──────────────────────────┴──▶ 400 {"error":"guardrail_rejection", ...}          │
│              PASS                                                                                  │
│                                              ▼                                                    │
│   3. hybrid_search(query, top_k)            │  backend/retrieval/searcher.py                       │
│      dense (e5-large, "query: " prefix)     │  → Qdrant query_points, RRF fusion, fetch_k=top_k*4  │
│      + sparse (BM25 fastembed)              │  (NO language filter — id + en both returned)        │
│                                              ▼                                                    │
│   3b. rerank(query, results, top_k)         │  backend/retrieval/searcher.py                       │
│      cross-encoder bge-reranker-v2-m3       │  scores each (query, chunk_text) pair, CUDA if avail │
│      fetch_k candidates → top_k kept        │                                                     │
│                                              ▼                                                    │
│   4. protect_output(results)                │  backend/guardrails/output.py                        │
│      truncate 500 chars, redact phrases,     │                                                     │
│      allowlist fields                        │                                                     │
│                                              ▼                                                    │
│   5. generate_answer(query, results, lang)  │  backend/generation/generator.py                     │
│      top-5 (reranked) chunks ──▶ OpenRouter  │  /chat/completions, fails open to ""                │
│                                              ▼                                                    │
│                          SearchResponse{answer, results, guardrail_checks,                        │
│                                          detected_lang, session_id, total_results}                 │
│                                              │                                                    │
│                                              ▼                                                    │
│                        (nothing currently consumes this response — call it                        │
│                                    directly, e.g. via curl or GET /docs)                           │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Batch pipeline (offline)

Run with `python run_pipeline.py`, or step by step with
`--step scrape|clean|chunk|embed|pdf`. Every step is idempotent — re-running
skips articles/chunks already stored. See
[alur-logic.md](alur-logic.md) for the detailed per-step breakdown and
[pipeline/README.md](pipeline/README.md).

## Online API (per request)

Implemented by `backend/main.py` (FastAPI app) and
`backend/routers/search.py` (`POST /api/search`, `GET /api/health`). The
request pipeline is strictly sequential and short-circuits on the first
guardrail failure — retrieval and generation only run once every input
guardrail check has passed:

1. **Session** (`backend/session.py`) — an in-memory `session_id → {history,
   created_at, last_active}` store, separate from PostgreSQL's
   `chat_sessions`/`chat_messages` tables (see
   [Two chat backends](#two-chat-backends-apichat-vs-apisearch) below).
   Sessions expire after 1 hour of inactivity and cap history at 20
   queries.
2. **Guardrails (input)** (`backend/guardrails/input.py`) —
   `run_input_guardrails()` runs `encoding → regex → injection → multiturn →
   scope → language_detect` in order, stopping at the first failure. See
   [guardrails.md](guardrails.md).
3. **Retrieval + reranking** (`backend/retrieval/searcher.py`) —
   `hybrid_search()` combines a dense e5-large vector and a sparse BM25
   vector via Qdrant's RRF fusion, over-fetching `top_k * 4` candidates,
   then `rerank()` scores each `(query, chunk_text)` pair with a
   cross-encoder (`BAAI/bge-reranker-v2-m3`, CUDA if available) and keeps
   only the top `top_k`. See [retrieval.md](retrieval.md).
4. **Guardrails (output)** (`backend/guardrails/output.py`) —
   `protect_output()` truncates, redacts, and field-allowlists every
   (already-reranked) result before it can reach the client or the
   generation step.
5. **Generation** (`backend/generation/generator.py`) — `generate_answer()`
   builds a grounded prompt from the top 5 reranked, protected chunks and
   calls OpenRouter (`RAG_GENERATOR_MODEL`). See [generation.md](generation.md).

Full request/response schema: [api.md](api.md).

## Two chat backends: `/api/chat` vs `/api/search`

`backend/main.py` exposes `POST /api/session`, `GET
/api/history/{session_id}`, and `POST /api/chat` — a simple, single-turn
chatbot API backed by `rag/pipeline.py` (`rag/retriever.py` +
`rag/generator.py`: hybrid dense+sparse retrieval via RRF, no reranking, no
guardrails) and persisted to PostgreSQL's `chat_sessions` / `chat_messages`
tables. **This is what the current React frontend
(`frontend/src/api/chat.ts`) actually calls.** Each source in its response
includes `article_id` (MD5-hashed) and the retrieved chunk's `content` text
(see [api.md](api.md#post-apichat)), which the frontend uses to deduplicate
source cards and render clickable links (see [frontend.md](frontend.md)).

`backend/routers/search.py` separately exposes `POST /api/search` and `GET
/api/health` — a more elaborate pipeline (guardrails → hybrid search →
cross-encoder rerank → output protection → generation, diagrammed above),
with its own in-memory session store (`backend/session.py`) unrelated to
`/api/chat`'s PostgreSQL-backed one (different store, no shared history;
the BGE query instruction is the only piece reused from the same
`config.py`). It still works end-to-end and is documented in full below and
in [guardrails.md](guardrails.md), [retrieval.md](retrieval.md), and
[generation.md](generation.md) — it's just not called by any UI right now.
`chatbot/app.py` (Streamlit) also talks to neither of these; it calls
`rag/pipeline.py` directly and remains for quick local testing.

## Frontend (chat UI)

`frontend/` is a React + TypeScript chat interface (`App.tsx` +
`ChatInput`/`ChatMessage` + `hooks/useChat.ts` + `api/chat.ts`) that calls
`POST /api/session` then `POST /api/chat` for every turn. See
[frontend.md](frontend.md).

## Evaluation pipeline

`evaluation/` scores the `/api/chat`-backed chatbot against a golden
Indonesian Q&A dataset:

- `evaluation/generate_dataset.py` samples articles from `clean_articles`
  and asks `DATASET_GENERATOR_MODEL` (via OpenRouter) to write 2-3 Indonesian
  Q&A pairs per article, writing `evaluation/golden_dataset_openrouter.csv`.
- `evaluation/evaluate.py` replays every question through `/api/chat`,
  then scores (question, answer, retrieved contexts, ground truth) with
  RAGAS (`faithfulness`, `answer_relevancy`, `context_precision`,
  `context_recall`) and DeepEval's `HallucinationMetric`. Both use
  `JUDGE_MODEL` (via OpenRouter) as the judge. Writes `evaluation/results.csv`
  with `generator_model` and `judge_model` columns.

See [evaluation.md](evaluation.md) for details on both scripts.

## Why PostgreSQL + Qdrant together

Qdrant stores the full retrieval payload — `chunk_text` included — alongside
the vectors, so neither `/api/chat` (`rag/retriever.py`) nor `/api/search`
(`backend/retrieval/searcher.py`) ever needs a PostgreSQL round-trip to
retrieve. PostgreSQL stores the same chunk/article data (written by the
batch pipeline) plus all `/api/chat` conversation history
(`chat_sessions`/`chat_messages`). `/api/search`'s own session/history store
(`backend/session.py`) is in-memory only and does not touch PostgreSQL.

## Embedding models

| Purpose | Model | Notes |
|---|---|---|
| Dense (indexing + query) | `intfloat/multilingual-e5-large` | Asymmetric: passages get `"passage: "`, queries get `"query: "` (`BGE_QUERY_INSTRUCTION` in `config.py`). 1024-dim, multilingual (id + en). |
| Sparse (indexing + query) | `Qdrant/bm25` via fastembed | Keyword/lexical matching. |
| Reranker (query-time only) | `BAAI/bge-reranker-v2-m3` | Cross-encoder; scores each `(query, chunk_text)` pair from RRF's fused candidates directly, multilingual. `config.RERANKER_MODEL_NAME` / `config.RERANKER_TOP_K`. |

The same model names are used both when indexing (`pipeline/embedder.py` →
`vectorization/embedder.py`) and when querying (`backend/retrieval/searcher.py`)
— they must stay in sync, since dense/sparse vectors from different model
versions are not comparable. See [retrieval.md](retrieval.md) for why the
model is multilingual and how that affects result language mixing.

## Local stack

| Component | Local Stack |
|---|---|
| Dense + sparse embedding | `intfloat/multilingual-e5-large` + BM25, native in-process (sentence-transformers / fastembed) |
| Reranking | `bge-reranker-v2-m3` cross-encoder, native in-process (sentence-transformers), CUDA if available else CPU |
| Generation | `RAG_GENERATOR_MODEL` (default `deepseek/deepseek-chat-v3-0324`) via OpenRouter (`/chat/completions`) |
| Guardrail scope/language classification | `GUARDRAIL_MODEL` (default `openai/gpt-4o-mini`) via OpenRouter |
| Dataset generation | `DATASET_GENERATOR_MODEL` (default `openai/gpt-4o-mini`) via OpenRouter |
| RAGAS / DeepEval judge | `JUDGE_MODEL` (default `google/gemini-2.5-flash`) via OpenRouter |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL |
| UI | React + TypeScript (chat), Streamlit (legacy) |
| Deployment | Docker Compose |

See [quickstart.md](quickstart.md) for how to bring the stack up.
