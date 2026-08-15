# Setup

## Prerequisites

- Python 3.10+
- A running PostgreSQL instance
- A running Qdrant instance (local via Docker, or Qdrant Cloud)
- An OpenAI API key with access to `text-embedding-3-small` and `gpt-4o-mini`
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
| `OPENAI_API_KEY` | OpenAI API key used for embeddings and GPT-4o-mini generation. |
| `POSTGRES_URL` | SQLAlchemy-style connection string, e.g. `postgresql://user:password@localhost:5432/newsrag`. |
| `QDRANT_URL` | Base URL of your Qdrant instance, e.g. `http://localhost:6333`. |
| `QDRANT_API_KEY` | API key for Qdrant Cloud; leave empty for a local instance without auth. |
| `GOOGLE_DRIVE_CREDENTIALS_PATH` | Path to a Google service account JSON key file, used by `pipeline/pdf_exporter.py`. |
| `NEWS_KEYWORDS` | Comma-separated list of keywords/topics to scrape from Google News. Each keyword is also used as the article's `category`. |

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

```bash
streamlit run chatbot/app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`) and start
asking questions about the scraped news.
