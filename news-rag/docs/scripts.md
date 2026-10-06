# Scripts

`scripts/` holds one-off and maintenance scripts that operate directly on
PostgreSQL and/or Qdrant, outside the regular `run_pipeline.py` flow. All
of them import `config.py` for connection details (`sys.path.insert` at the
top of each file), so run them from the project root, or inside the
backend/pipeline container where `config.py`'s env vars already resolve to
the in-network `postgres`/`qdrant` hosts.

## `delete_articles_by_title.py` — manual article cleanup

The reusable one: deletes any article(s) matching a SQL `ILIKE` pattern
against `clean_articles.title`, and keeps all three stores in sync —
Qdrant points (filtered by `article_id`), `chunks`, `clean_articles`, and
the corresponding `raw_articles` row.

```bash
python scripts/delete_articles_by_title.py "%myanmar%meth%"        # lists matches, asks to confirm
python scripts/delete_articles_by_title.py "%myanmar%meth%" --yes  # skip the confirmation prompt
```

Use this whenever an article turns out to be off-topic, mis-scraped, or
otherwise needs to be pulled from the live knowledge base — it's the
supported way to remove something (rather than deleting rows from
PostgreSQL and Qdrant by hand and risking one store falling out of sync
with the other).

## `ingest_knowledge/pdf_ingestor.py`: manual PDF ingestion

Ingests PDF files as knowledge-base chunks, outside the scraping pipeline.
It extracts text per page (PyMuPDF, with OCR through `pytesseract` for pages
without a text layer), removes header and footer noise, chunks the text, and
writes each chunk to PostgreSQL and its dense vector to Qdrant.

| Item | Value |
|---|---|
| Dense model | `DENSE_MODEL_NAME`, default `intfloat/multilingual-e5-large`, with the `passage: ` prefix |
| Qdrant | `QDRANT_URL` (default `http://localhost:6335`), collection `COLLECTION_NAME` (default `data-paper-child`) |
| PostgreSQL | `POSTGRES_HOST`, `POSTGRES_PORT` (script default `5433`), `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |

| Command | Effect |
|---|---|
| `python ingest_knowledge/pdf_ingestor.py --dry-run` | Previews the ingest. Writes nothing. |
| `python ingest_knowledge/pdf_ingestor.py --file <name.pdf>` | Ingests one file, matched by filename. |
| `python ingest_knowledge/pdf_ingestor.py` | Ingests every PDF it finds. |

The chunks carry `source_type` `pdf_knowledge`, which is the same value the
evaluation dataset uses for PDF-sourced questions.

## One-off data-fix scripts

The rest were written to resolve specific data issues found in the
`drive_reviewed` article batch (articles manually uploaded outside the
normal `scraper.py` → `cleaner.py` → `sync_reviewed.py` flow) and are kept
for reference/audit trail rather than routine reuse:

| Script | Fixed |
|---|---|
| `backfill_drive_reviewed.py` | Missing `source`/`date` on `drive_reviewed` articles, parsed from filename/content (`--apply` to write; preview-only otherwise). |
| `apply_drive_reviewed_curation.py` | Applies a hardcoded, human-reviewed KEEP/DELETE list for 25 `drive_reviewed` articles. |
| `apply_orphan_drive_reviewed.py` | Same, for 34 `drive_reviewed` articles found in Qdrant with no backing `clean_articles` row (fixes the Qdrant payload directly, since the live serving path reads title/source/date/url straight from Qdrant). |
| `remove_drive_reviewed_duplicates.py` | Removes 3 `drive_reviewed` rows confirmed to be re-uploaded duplicates of articles the scraper had already collected. |
| `backfill_url_payload.py` | Backfills the Qdrant payload's `url` field (left at an old `drive_reviewed://` placeholder by `apply_drive_reviewed_curation.py`) for 10 KEEP articles — needed once the frontend started rendering sources as clickable links (see [frontend.md](frontend.md)), since a placeholder URL can't be linked to. |

If you hit a similar one-off data-integrity issue, these are worth reading
as examples of the KEEP/DELETE-list-plus-dry-run pattern used throughout,
rather than reusing directly.
