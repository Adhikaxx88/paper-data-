# Setup

The pipeline and chatbot run entirely on a **local, self-hosted stack** by
default: [infinity-emb](https://github.com/michaelfeil/infinity) serves BGE
embeddings and [Ollama](https://ollama.com) serves the LLM, so no OpenAI API
key is required. The easiest way to run everything is
[Docker Compose](#running-with-local-stack-docker) — see that section below.
The rest of this page covers running each piece manually without Docker.

## Prerequisites

- Python 3.10+
- A running PostgreSQL instance
- A running Qdrant instance (local via Docker, or Qdrant Cloud)
- A local embedding server compatible with the OpenAI `/embeddings` API,
  serving `BAAI/bge-large-en-v1.5` (e.g. infinity-emb) — see
  [Embedder](pipeline/embedder.md)
- A local Ollama instance with a model pulled (default `llama3.1`) — see
  [Generator](rag/generator.md)
- (Optional) An OpenAI API key, only if you point `pipeline/embedder.py` /
  `rag/generator.py` back at OpenAI instead of the local stack
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
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure `.env`

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Optional. Only used if you switch `pipeline/embedder.py` / `rag/generator.py` back to OpenAI-hosted models. |
| `POSTGRES_URL` | Connection string, e.g. `postgresql://user:password@localhost:5432/newsrag` (use `postgres` as the host under Docker Compose). |
| `QDRANT_URL` | Base URL of your Qdrant instance, e.g. `http://localhost:6333` (`http://qdrant:6333` under Docker Compose). |
| `QDRANT_API_KEY` | API key for Qdrant Cloud; leave empty for a local instance without auth. |
| `GOOGLE_DRIVE_CREDENTIALS_PATH` | Path to a Google service account JSON key file, used by `pipeline/pdf_exporter.py`. |
| `NEWS_KEYWORDS` | Comma-separated list of keywords/topics to scrape from Google News. Each keyword is also used as the article's `category`. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credentials used by the `postgres` container in `docker-compose.yml`; must match the values embedded in `POSTGRES_URL`. |
| `INFINITY_URL` | Base URL of the infinity-emb embedding server, e.g. `http://infinity:7997` under Docker Compose. |
| `EMBED_MODEL` | Embedding model served by infinity-emb. Default `BAAI/bge-large-en-v1.5`. |
| `EMBED_DIM` | Vector dimension of `EMBED_MODEL`, used to size the Qdrant collection. Default `1024` (BGE-large). Must match the model — see the warning in the [Docker section](#running-with-local-stack-docker) below if you change it. |
| `OLLAMA_URL` | OpenAI-compatible base URL of your Ollama instance, e.g. `http://ollama:11434/v1` under Docker Compose. |
| `OLLAMA_MODEL` | Model name to use for generation, e.g. `llama3.1`. Must already be pulled in Ollama. |

## Initialize the database

```bash
psql $POSTGRES_URL -f db/schema.sql
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
infinity-emb (BGE embeddings), Ollama (LLM), the batch pipeline, the FastAPI
backend, and the React frontend, all wired together by `docker-compose.yml`.

### Prerequisites

- Docker + Docker Compose (v2)
- **At least 16GB RAM** available to Docker. Rough footprint:
  - BGE-large-en-v1.5 (infinity-emb): ~1.3GB
  - Llama 3.1 (Ollama): ~4.7GB
  - PostgreSQL + Qdrant + backend/frontend: ~2GB
  - Leaves headroom for model inference, which is the biggest variable cost

### First-time setup

```bash
cp .env.example .env   # adjust POSTGRES_*, keywords, etc. as needed

# 1. Bring up the data + model-serving layer
docker compose up -d postgres qdrant infinity ollama

# 2. Pull the LLM (one-shot; waits for ollama to be healthy)
docker compose run ollama-init

# 3. Run the batch pipeline once to scrape + index articles
docker compose run pipeline python run_pipeline.py

# 4. Bring up the API and UI
docker compose up backend frontend
```

### How to access

Open the chatbot at **`http://localhost:3000`**. The FastAPI backend is
reachable directly at `http://localhost:8000` (e.g. `GET /docs` for the
OpenAPI schema).

### Re-running the pipeline later

The `pipeline` service uses the `pipeline` Compose profile, so it never
starts as part of `docker compose up` — run it on demand:

```bash
docker compose run pipeline python run_pipeline.py --step scrape
```

### Switching the Ollama model

1. Update `OLLAMA_MODEL` in `.env`.
2. Pull the new model into the running Ollama container:

   ```bash
   docker compose run ollama ollama pull <model>
   ```

3. Restart the backend so it picks up the new `.env` value:

   ```bash
   docker compose restart backend
   ```

### Switching embedding models (OpenAI → BGE, or BGE → a different model)

!!! warning
    Qdrant collections have a fixed vector dimension. Switching
    `EMBED_MODEL` to a model with a different `EMBED_DIM` **will** cause
    dimension-mismatch errors until the collection is recreated.

```bash
# 1. Update EMBED_MODEL / EMBED_DIM in .env to match the new model
# 2. Drop and recreate the Qdrant collection at the new dimension
docker compose run backend python -c "from db.qdrant_client import recreate_collection; recreate_collection()"
# 3. Re-embed everything (PostgreSQL text/article data is untouched and reused)
docker compose run pipeline python run_pipeline.py --step embed
```
