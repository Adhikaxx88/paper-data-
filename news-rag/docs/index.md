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
  an LLM served through OpenRouter (DeepSeek V3 by default) to answer strictly
  from that context, citing sources.
- **Evaluates itself** against a golden Indonesian Q&A dataset with RAGAS
  (faithfulness, answer relevancy, context precision/recall) and DeepEval
  (hallucination), judged by a separate model on OpenRouter — see
  [Evaluation](evaluation.md).

Embeddings and reranking stay local (multilingual-e5-large, BM25, bge-reranker-v2-m3).
All LLM calls (generation, guardrails, dataset generation, judge) go through OpenRouter.

## Who it's for

Anyone who wants a self-hosted, source-cited news Q&A chatbot over a topic
they care about (e.g. fintech regulation, a specific industry, a running news
story) without relying on a third-party search API.

## Quick start

```bash
cp .env.example .env          # then set OPENROUTER_API_KEY
docker compose up -d postgres qdrant
docker compose run pipeline python run_pipeline.py
docker compose up backend frontend   # chatbot at http://localhost:3000
```

See [Setup](setup.md) for prerequisites, running without Docker, and full
configuration details.
