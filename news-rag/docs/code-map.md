# Code map

Which code file does what, and which docs page explains it. Use this to find
the code behind a claim in the docs. Paths are relative to the repo root.

## Entry points and configuration

| File | Main functions or content | Purpose | Docs |
|---|---|---|---|
| `config.py` | Module constants read from env | All settings: models, ports, `RETRIEVAL_TOP_K`, `provider_body()` (OpenRouter provider pin) | [quickstart.md](quickstart.md#env-vars-needed), [setup.md](setup.md) |
| `run_pipeline.py` | `run_scrape`, `run_clean`, `run_chunk`, `run_embed`, `run_pdf`, `run_all`, `main` | CLI for the batch pipeline (`--step`) | [cara-run.md](cara-run.md), [pipeline/README.md](pipeline/README.md) |
| `setup-db.py` | `apply_schema`, `verify_tables` | Creates PostgreSQL tables from `db/schema.sql` | [setup.md](setup.md), [database/postgres.md](database/postgres.md) |
| `sync_reviewed.py` | `sync`, `_delete_rejected` | Syncs reviewed files from Google Drive, deletes rejected articles | [cara-run.md](cara-run.md), [scripts.md](scripts.md) |
| `docker-compose.yml` | Services `postgres`, `qdrant`, `backend`, `frontend`, `pipeline` (profile `pipeline`), `evaluation` (profile `evaluation`) | Container layout and host ports (see below) | [setup.md](setup.md#running-with-local-stack-docker), [cara-run.md](cara-run.md) |
| `Dockerfile.backend`, `Dockerfile.pipeline` | Image builds for backend and pipeline or evaluation | Container images | [setup.md](setup.md) |
| `requirements.txt` | Root dependencies (pipeline, evaluation) | Install for host-side runs | [evaluation.md](evaluation.md#dependencies) |
| `backend/requirements.txt` | Backend dependencies | Install for the FastAPI backend | [quickstart.md](quickstart.md) |
| `START.md` | Quick-start steps | Short version of the quickstart | [quickstart.md](quickstart.md) |

### Host ports

| Service | Container port | Host port | Source |
|---|---|---|---|
| `postgres` | 5432 | 5433 | `docker-compose.yml` |
| `qdrant` | 6333 | 6335 | `docker-compose.yml` |
| `backend` | 8000 | 8686 | `docker-compose.yml` |
| `frontend` (Vite dev server) | 5173 | 5888 | `docker-compose.yml` |

Native (non-Docker) runs use the same defaults as `config.py`: `QDRANT_URL`
defaults to `localhost:6335`. The backend port depends on how uvicorn is
started (see [quickstart.md](quickstart.md#2-start-the-backend)).

## Batch pipeline (`pipeline/`)

| File | Functions | Purpose | Docs |
|---|---|---|---|
| `pipeline/scraper.py` | `fetch_and_store`, `_fetch_rss`, `_extract_content` | Google News RSS scrape into `raw_articles` | [pipeline/scraper.md](pipeline/scraper.md) |
| `pipeline/cleaner.py` | `clean_and_store`, `_is_indonesia_relevant` | Cleans text, filters by relevance, writes `clean_articles` | [pipeline/cleaner.md](pipeline/cleaner.md) |
| `pipeline/chunker.py` | `chunk_articles`, `_split_into_chunks`, `_derive_chunk_id` | Token-based overlapping chunks | [pipeline/chunker.md](pipeline/chunker.md) |
| `pipeline/embedder.py` | `embed_and_store`, `_store_in_postgres` | Embeds chunks and writes them to PostgreSQL and Qdrant | [pipeline/embedder.md](pipeline/embedder.md) |
| `pipeline/pdf_exporter.py` | `export_and_upload`, `_create_pdf` | Builds per-article PDFs and uploads to Google Drive | [pipeline/pdf_exporter.md](pipeline/pdf_exporter.md) |
| `ingest_knowledge/pdf_ingestor.py` | `ingest_pdf`, `extract_pdf`, `build_chunks_from_pages`, `main` | Manual PDF ingestion (PyMuPDF, OCR) | [scripts.md](scripts.md#ingest_knowledgepdf_ingestorpy-manual-pdf-ingestion) |

## Embedding and vector store (`vectorization/`, `db/`)

| File | Functions | Purpose | Docs |
|---|---|---|---|
| `vectorization/embedder.py` | `get_dense_model`, `get_sparse_model`, `encode_passage`, `encode_query`, `encode_sparse` | Dense (`multilingual-e5-large`) and BM25 sparse encoders, in-process | [retrieval.md](retrieval.md), [architecture.md](architecture.md) |
| `vectorization/qdrant_store.py` | `get_client`, `init_collection`, `recreate_collection`, `upsert_chunks`, `point_exists` | Qdrant collection management and writes | [database/qdrant.md](database/qdrant.md) |
| `db/postgres.py` | `init_schema`, `upsert_article`, `insert_chunk`, `create_session`, `insert_message`, `get_recent_messages`, and related helpers | PostgreSQL access | [database/postgres.md](database/postgres.md) |
| `db/schema.sql` | Table definitions | Schema for articles, chunks, sessions, messages | [database/postgres.md](database/postgres.md) |

## RAG and backend (`rag/`, `backend/`)

| File | Functions | Purpose | Docs |
|---|---|---|---|
| `rag/retriever.py` | `retrieve` | Retrieval for `/api/chat` (called from `rag/pipeline.py`) | [rag/retriever.md](rag/retriever.md) |
| `rag/generator.py` | `generate_answer`, `build_messages`, `build_context_block` | Answer generation via OpenRouter (`RAG_GENERATOR_MODEL`) | [rag/generator.md](rag/generator.md) |
| `rag/pipeline.py` | `ask` | `/api/chat` flow: retrieve, then generate | [rag/pipeline.md](rag/pipeline.md) |
| `backend/main.py` | `create_session`, `get_history`, `chat`, `SourceOut`, `ChatResponse` | FastAPI app and `/api/session`, `/api/history/{id}`, `/api/chat` | [api.md](api.md) |
| `backend/routers/search.py` | `SearchRequest`, `SearchResponse`, `/search`, `/health` | `/api/search` and `/api/health` | [api.md](api.md) |
| `backend/retrieval/searcher.py` | `hybrid_search`, `get_reranker`, `rerank` | Dense plus BM25, RRF fusion, cross-encoder rerank | [retrieval.md](retrieval.md) |
| `backend/generation/generator.py` | `generate_answer` | Answer generation for `/api/search` | [generation.md](generation.md) |
| `backend/guardrails/input.py` | `run_input_guardrails`, `scope_check`, `language_detect`, `injection_check`, `multiturn_check`, `encoding_check`, `regex_check` | Input checks, scope and language via `GUARDRAIL_MODEL` | [guardrails.md](guardrails.md) |
| `backend/guardrails/output.py` | `protect_output` | Output checks on the generated answer | [guardrails.md](guardrails.md) |
| `backend/session.py` | `get_or_create_session`, `append_to_session`, `get_history` | In-memory `sessions` dict with expiry (`_is_expired`) | [architecture.md](architecture.md) |

## Evaluation (`evaluation/`)

| File | Functions | Purpose | Docs |
|---|---|---|---|
| `evaluation/generate_dataset.py` | `build_dataset`, `allocate_questions`, `generate_qa_for_article`, `parse_qa_pairs`, `write_csv`, `main` | Golden Q&A dataset (2500 target pairs) | [evaluation.md](evaluation.md#generate_datasetpy-building-the-golden-dataset) |
| `evaluation/evaluate.py` | `run_ragas`, `run_deepeval_hallucination`, `collect_rag_outputs`, `query_chat_api`, `_ragas_score_in_process`, `with_retry`, `print_summary`, `main` | Scores `/api/chat` answers with RAGAS and DeepEval | [evaluation.md](evaluation.md#evaluatepy-scoring-the-chatbot) |
| `evaluation/golden_dataset_openrouter.csv` | Dataset | Output of `generate_dataset.py` | [evaluation.md](evaluation.md) |
| `evaluation/runs/` | Checkpoints, `failed_rows.json`, `results.csv` | Run outputs per `EVAL_RUN_DIR` | [evaluation.md](evaluation.md#run-directory-and-files) |

## Frontend (`frontend/src/`)

| File | Purpose | Docs |
|---|---|---|
| `main.tsx`, `App.tsx` | Entry point and layout | [frontend.md](frontend.md) |
| `api/chat.ts` | `createSession`, `sendChatMessage`; base URL from `VITE_API_URL` (default `http://localhost:8686`) | [frontend.md](frontend.md) |
| `hooks/useChat.ts` | Chat state and request flow | [frontend.md](frontend.md) |
| `components/ChatInput.tsx`, `components/ChatMessage.tsx` | Input box and message rendering | [frontend.md](frontend.md) |
| `types/chat.ts` | `ChatMessage`, `SourceItem`, `ChatResponse` types | [frontend.md](frontend.md), [api.md](api.md) |
| `vite.config.ts` | Dev server, proxy `/api` to `http://localhost:8686` | [frontend.md](frontend.md) |

## Chatbot and scripts

| File | Purpose | Docs |
|---|---|---|
| `chatbot/app.py` | Streamlit chatbot (alternative UI) | [cara-run.md](cara-run.md) |
| `scripts/*.py` | One-off data-fix scripts (delete, backfill, drive-reviewed curation) | [scripts.md](scripts.md) |

## Documentation files

| File | Covers |
|---|---|
| `index.md` | Overview |
| `quickstart.md`, `setup.md`, `cara-run.md`, `struktur-file.md` | Running the system and the file layout |
| `architecture.md`, `alur-logic.md` | Design and data flow |
| `pipeline/*.md`, `vectorization/README.md`, `data/README.md` | Batch pipeline and data |
| `retrieval.md`, `generation.md`, `guardrails.md`, `rag/*.md` | Chat answer path |
| `api.md`, `frontend.md` | HTTP API and UI |
| `database/*.md`, `db/README.md` | PostgreSQL and Qdrant |
| `evaluation.md` | Evaluation method and scripts |
| `scripts.md` | Maintenance scripts and PDF ingestion |
| `mkdocs.yml` | MkDocs site config |
