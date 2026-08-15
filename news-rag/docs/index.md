# News RAG Chatbot

A complete Retrieval-Augmented Generation (RAG) pipeline for a news chatbot. It
scrapes Google News, cleans and chunks the articles, embeds and stores them in
PostgreSQL + Qdrant, backs up PDFs to Google Drive, and serves answers through
a chat interface grounded in the retrieved articles — running entirely on a
local, self-hosted model stack by default.

## What it does

- **Scrapes** Google News for a configurable list of keywords.
- **Cleans and chunks** article text into overlapping, token-sized pieces.
- **Embeds** each chunk with a local BGE model (`BAAI/bge-large-en-v1.5` via
  infinity-emb) and stores the vector in Qdrant, with the text kept in
  PostgreSQL.
- **Backs up** each article as a categorized PDF in Google Drive.
- **Answers questions** by retrieving the most relevant chunks and asking a
  local LLM (Llama 3.1 via Ollama) to answer strictly from that context,
  citing sources.

Cloud models (OpenAI embeddings + GPT-4o-mini) are still supported as a swap-in
alternative — see [Architecture](architecture.md#cloud-stack-vs-local-stack).

## Who it's for

Anyone who wants a self-hosted, source-cited news Q&A chatbot over a topic
they care about (e.g. fintech regulation, a specific industry, a running news
story) without relying on a third-party search API.

## Quick start

```bash
cp .env.example .env
docker compose up -d postgres qdrant infinity ollama
docker compose run ollama-init
docker compose run pipeline python run_pipeline.py
docker compose up backend frontend   # chatbot at http://localhost:3000
```

See [Setup](setup.md) for prerequisites, running without Docker, and full
configuration details.
