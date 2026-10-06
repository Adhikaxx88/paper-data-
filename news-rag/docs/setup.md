# Setup

Embeddings and reranking run locally, and **all LLM calls go through
[OpenRouter](https://openrouter.ai)** (generation, guardrails, dataset
generation, and evaluation judge), so an OpenRouter API key is required. The
easiest way to run everything is
[Docker Compose](#running-with-local-stack-docker) — see that section below.
The rest of this page covers running each piece manually without Docker.

## Prerequisites

- Python 3.10+
- A running PostgreSQL instance
- A running Qdrant instance (local via Docker, or Qdrant Cloud)
- No separate embedding server. The dense, sparse, and reranker models load
  in-process (see [Embedder](pipeline/embedder.md)).
- An OpenRouter API key (`OPENROUTER_API_KEY`) — see
  [Generator](rag/generator.md)
- (Optional) A Google Cloud service account with Drive API access, if you
  want PDF backups uploaded to Drive

### Running Qdrant locally

```bash
docker run -p 6333:6333 qdrant/qdrant
```

## Installation

```bash
git clone <this-repo>
cd news-rag
python -m venv .venv && source .venv/bin/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure `.env`

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | Required. Key for OpenRouter, used by every LLM call (generation, guardrails, dataset generator, judge). Keep it in `.env` only. |
| `OPENROUTER_BASE_URL` | Defaults to `https://openrouter.ai/api/v1`. |
| `RAG_GENERATOR_MODEL` | Model for answer generation, e.g. `deepseek/deepseek-chat-v3-0324`. |
| `GUARDRAIL_MODEL` | Cheap model for `scope_check` / `language_detect`, e.g. `openai/gpt-4o-mini`. Runs on every `/api/search` query. |
| `DATASET_GENERATOR_MODEL` | Model that writes the golden Q&A dataset, e.g. `openai/gpt-4o-mini`. |
| `JUDGE_MODEL` | Model that judges RAGAS and DeepEval metrics, e.g. `google/gemini-2.5-flash`. |
| `QDRANT_URL` | Base URL of your Qdrant instance, e.g. `http://localhost:6335` (`http://qdrant:6333` under Docker Compose). |
| `QDRANT_API_KEY` | API key for Qdrant Cloud; leave empty for a local instance without auth. |
| `GOOGLE_DRIVE_CREDENTIALS_PATH` | Path to a Google service account JSON key file, used by `pipeline/pdf_exporter.py`. |
| `NEWS_KEYWORDS` | Comma-separated list of keywords/topics to scrape from Google News. Each keyword is also used as the article's `category`. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_HOST` / `POSTGRES_PORT` | Individual components used by both the `postgres` container in `docker-compose.yml` and `config.py`, which assembles them into the connection string (`POSTGRES_HOST` defaults to `127.0.0.1`, `POSTGRES_PORT` to `5432`; use `postgres` as the host under Docker Compose). |
| `DENSE_MODEL_NAME` | Dense embedding model, loaded in-process with sentence-transformers. Default `intfloat/multilingual-e5-large`. |
| `SPARSE_MODEL_NAME` | BM25 sparse model, loaded in-process with fastembed. Default `Qdrant/bm25`. |
| `EMBED_DIM` | Vector dimension of `DENSE_MODEL_NAME`, used to size the Qdrant collection. Default `1024`, the output size of `intfloat/multilingual-e5-large`. Must match the model — see the warning in the [Docker section](#running-with-local-stack-docker) below if you change it. |

## Initialize the database

```bash
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}/$POSTGRES_DB" -f db/schema.sql
```

This creates `articles`, `chunks`, `chat_sessions`, and `chat_messages`.
`pipeline/embedder.py` also calls this automatically on first run via
`db.postgres.init_schema()`, so manual execution is optional but recommended
for visibility into the schema.

## Run the pipeline

```bash
python run_pipeline.py               # run all steps: scrape -> clean -> chunk -> embed -> pdf
python run_pipeline.py --step scrape # run a single step
```

## Run the chatbot

A Streamlit chatbot (`chatbot/app.py`) is still available for quick local
testing without Docker or a frontend build:

```bash
streamlit run chatbot/app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`) and start
asking questions about the scraped news. The production UI is the React
frontend described in [Frontend](frontend.md), served via the `frontend`
service below.

## Running with Local Stack (Docker)

This is the recommended way to run the whole system: PostgreSQL, Qdrant,
the batch pipeline, the FastAPI backend, and the
React frontend, all wired together by `docker-compose.yml`. LLM calls go to
OpenRouter, so there is no LLM container.

### Prerequisites

- Docker + Docker Compose (v2)
- An OpenRouter API key in `.env` (`OPENROUTER_API_KEY`)
- **At least 16GB RAM** available to Docker. Rough footprint:
  - `intfloat/multilingual-e5-large` (sentence-transformers, downloaded on first use)
  - PostgreSQL + Qdrant + backend/frontend: ~2GB
  - Leaves headroom for the embedding and reranking models

### First-time setup

```bash
cp .env.example .env   # set OPENROUTER_API_KEY, POSTGRES_*, keywords, etc.

# 1. Bring up the data layer
docker compose up -d postgres qdrant

# 2. Run the batch pipeline once to scrape + index articles
docker compose run pipeline python run_pipeline.py

# 3. Bring up the API and UI
docker compose up backend frontend
```

### How to access

Open the chatbot at **`http://localhost:5888`**. The `frontend` service
runs the Vite dev server directly inside the container (`node:20-slim`,
`npm run dev -- --host 0.0.0.0`) rather than a built/nginx-served bundle, so
the container port 5173 is published as host port 5888. Local `npm run dev`
uses 5173. The FastAPI backend is published at `http://localhost:8686` (e.g. `GET /docs` for the
OpenAPI schema).

### Re-running the pipeline later

The `pipeline` service uses the `pipeline` Compose profile, so it never
starts as part of `docker compose up` — run it on demand:

```bash
docker compose run pipeline python run_pipeline.py --step scrape
```

### Switching the LLM model

Each role has its own variable in `.env`. Nothing needs to be pulled, since the
model is served by OpenRouter.

1. Update `RAG_GENERATOR_MODEL`, `GUARDRAIL_MODEL`, `DATASET_GENERATOR_MODEL`,
   or `JUDGE_MODEL` in `.env`. Use an OpenRouter model slug (`provider/model`).
2. Restart the backend so it picks up the new `.env` value:

   ```bash
   docker compose restart backend
   ```

If you change `DATASET_GENERATOR_MODEL` or `JUDGE_MODEL`, or the generator
model whose answers are being scored, follow the checkpoint reset steps in
[evaluation.md](evaluation.md) before re-running the evaluation.

### Switching embedding models (OpenAI → BGE, or BGE → a different model)

!!! warning
    Qdrant collections have a fixed vector dimension. Switching
    `DENSE_MODEL_NAME` to a model with a different `EMBED_DIM` **will** cause
    dimension-mismatch errors until the collection is recreated.

```bash
# 1. Update DENSE_MODEL_NAME / EMBED_DIM in .env to match the new model
# 2. Drop and recreate the Qdrant collection at the new dimension
docker compose run backend python -c "from vectorization.qdrant_store import recreate_collection; recreate_collection()"
# 3. Re-embed everything (PostgreSQL text/article data is untouched and reused)
docker compose run pipeline python run_pipeline.py --step embed
```

### Model caches

`docker-compose.yml` mounts three named volumes so downloaded models
survive container restarts instead of re-downloading every time:
`hf_cache` (HuggingFace Hub, used by the dense e5 model and the
`bge-reranker-v2-m3` cross-encoder), `st_cache` (sentence-transformers), and
`fastembed_cache` (the BM25 sparse model — fastembed ignores `HF_HOME` and
defaults to `/tmp/fastembed_cache`, which doesn't survive a container
recreate without an explicit mount). All three are shared between the
`pipeline` and `backend` services.

## Running the evaluation pipeline

See [evaluation.md](evaluation.md) for the full walkthrough. Short version:

```bash
# Generate the golden Q&A dataset (inside Docker)
docker compose run evaluation python evaluation/generate_dataset.py

# Score the chatbot against it (from the host; EVAL_CHAT_API_BASE sets the backend URL)
python -m evaluation.evaluate
```

## Manual article cleanup

To remove one or more articles (and their chunks/vectors) by a title
pattern, from PostgreSQL and Qdrant together:

```bash
python scripts/delete_articles_by_title.py "%myanmar%meth%"       # prompts for confirmation
python scripts/delete_articles_by_title.py "%myanmar%meth%" --yes # skip the prompt
```

See [scripts.md](scripts.md) for this and the other one-off data-fix
scripts in `scripts/`.

## Frontend Development

The FastAPI backend (`backend/main.py`) must be running for the frontend to
have anything to talk to — either via Docker (`docker compose up -d postgres
qdrant && docker compose up backend`) or locally
(`uvicorn backend.main:app --reload --port 8686`).

Then, for hot-reloading frontend development outside Docker:

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, proxies /api to :8686
```

See [Frontend](frontend.md) for the component structure and how the UI talks
to the backend.
