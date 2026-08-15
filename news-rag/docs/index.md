# News RAG Chatbot

A complete Retrieval-Augmented Generation (RAG) pipeline for a news chatbot. It
scrapes Google News, cleans and chunks the articles, embeds and stores them in
PostgreSQL + Qdrant, backs up PDFs to Google Drive, and serves answers through
a Streamlit chat interface grounded in the retrieved articles.

## What it does

- **Scrapes** Google News for a configurable list of keywords.
- **Cleans and chunks** article text into overlapping, token-sized pieces.
- **Embeds** each chunk with OpenAI `text-embedding-3-small` and stores the
  vector in Qdrant, with the text kept in PostgreSQL.
- **Backs up** each article as a categorized PDF in Google Drive.
- **Answers questions** by retrieving the most relevant chunks and asking
  GPT-4o-mini to answer strictly from that context, citing sources.

## Who it's for

Anyone who wants a self-hosted, source-cited news Q&A chatbot over a topic
they care about (e.g. fintech regulation, a specific industry, a running news
story) without relying on a third-party search API.

## Quick start

```bash
pip install -r requirements.txt
psql $POSTGRES_URL -f db/schema.sql
python run_pipeline.py
streamlit run chatbot/app.py
```

See [Setup](setup.md) for prerequisites and full configuration details.
