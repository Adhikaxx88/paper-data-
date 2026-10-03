# Quickstart

Expanded from the root-level [`START.md`](../START.md) — same steps, with
the `.env` variables the guardrailed search API needs spelled out.

## 1. Start Docker services

PostgreSQL and Qdrant run as containers; the pipeline and backend run natively
via `sentence-transformers`/`fastembed` for direct GPU access (see
`docker-compose.yml`'s top comment). All LLM calls go to OpenRouter, so no
LLM container is needed:

```bash
docker compose up -d postgres qdrant
```

## 2. Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Or, on Windows, `backend\start.bat` runs the same command. This also works
as `uvicorn backend.main:app --reload` from the project root (what
`docker-compose.yml`'s `backend` service does) — `backend/main.py` inserts
the project root onto `sys.path` at import time so both entry points
resolve `config`, `db`, `rag`, `vectorization`, and `backend.*` correctly.

Serves at `http://localhost:8000`. Check it's healthy:

```bash
curl http://localhost:8000/api/health
```

## 3. Start the frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Or `frontend\start.bat` on Windows. Serves at `http://localhost:5173`,
proxying `/api/*` to `http://localhost:8000` (`vite.config.ts`).

## 4. Open the app

- Dev (`npm run dev` outside Docker): **http://localhost:5173**
- Docker (`docker compose up backend frontend`): also **http://localhost:5173** — the
  `frontend` service in `docker-compose.yml` runs the Vite dev server itself
  (`node:20-slim`, `npm run dev -- --host 0.0.0.0`), not a built/nginx-served
  bundle, so both paths land on the same port. See
  [Setup#running-with-local-stack-docker](setup.md#running-with-local-stack-docker).

## Env vars needed

Set in `.env` at the project root, loaded once by `config.py` via
`python-dotenv`. Every backend file imports these constants from
`config.py` rather than calling `os.getenv()` itself, so there's a single
source of truth for each value:

| Variable | Default if unset | Used by |
|---|---|---|
| `OPENROUTER_API_KEY` | (empty — required) | `config.py` → `rag/generator.py` (`/api/chat`, Streamlit), `backend/generation/generator.py` (`/api/search`), `backend/guardrails/input.py` (`scope_check`, `language_detect`), `backend/routers/search.py` (`GET /api/health`), `evaluation/` (dataset, judge) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Same as above |
| `RAG_GENERATOR_MODEL` | `deepseek/deepseek-chat-v3-0324` | Answer generation for `/api/chat`, `/api/search`, and Streamlit |
| `GUARDRAIL_MODEL` | `openai/gpt-4o-mini` | `scope_check` and `language_detect` on every `/api/search` query |
| `DATASET_GENERATOR_MODEL` | `openai/gpt-4o-mini` | `evaluation/generate_dataset.py` |
| `JUDGE_MODEL` | `google/gemini-2.5-flash` | `evaluation/evaluate.py` (RAGAS and DeepEval) |
| `QDRANT_URL` | `http://localhost:6333` | `config.py` → `vectorization/qdrant_store.py`, reused by `backend/retrieval/searcher.py` |
| `COLLECTION_NAME` | `data-paper-child` | Qdrant collection name (`config.QDRANT_COLLECTION`) |
| `RETRIEVAL_TOP_K` | `5` | `config.py` → default `top_k` for `backend/retrieval/searcher.py:hybrid_search()` and `SearchRequest.top_k` |
| `CONVERSATION_HISTORY_LIMIT` | `10` | `config.py` → caps the history window `backend/routers/search.py` passes into `run_input_guardrails()` |
| `DENSE_MODEL_NAME` | `intfloat/multilingual-e5-large` | Dense embedding model, indexing and query sides both |
| `SPARSE_MODEL_NAME` | `Qdrant/bm25` | BM25 sparse embedding model, indexing and query sides both |
| `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-v2-m3` | Cross-encoder reranker, query side only — `backend/retrieval/searcher.py:get_reranker()` |
| `RERANKER_TOP_K` | `5` | `rerank()`'s default number of results kept after reranking |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_HOST` / `POSTGRES_PORT` | see `.env.example` | `config.POSTGRES_URL`, used by the batch pipeline and the legacy `/api/chat` path |

`RERANKER_MODEL_NAME` is downloaded and loaded lazily (on the first search
request, not at backend startup) — expect a one-time delay on that first
request while `sentence-transformers` pulls the model.

`OPENROUTER_API_KEY` must be set in `.env` before starting the backend. If it's
empty or invalid, `/api/search` keeps working, but the guardrail LLM checks
fail open and log a WARNING on every query, and `/api/health` reports
`"openrouter": false`.

`.env.example` at the project root lists every key (blank) — copy it and
fill in real values:

```bash
cp .env.example .env
```

## Also see

- [architecture.md](architecture.md) — full system diagram
- [api.md](api.md) — `/api/search` and `/api/health` request/response schemas
- [guardrails.md](guardrails.md) — what each input/output check does
- [retrieval.md](retrieval.md) — hybrid dense+sparse search
- [generation.md](generation.md) — how the answer is generated
- [frontend.md](frontend.md) — chat UI components
