# PDF Exporter

`pipeline/pdf_exporter.py`

## What it does

Renders each cleaned article as a PDF (title, source/date/url header, and
full content) using `fpdf2`, saves it locally organized by category, then
uploads it to Google Drive and records the resulting shareable link on the
article's row in PostgreSQL (`articles.drive_url`).

## Naming and folder organization

Local files are written to:

```
data/pdf/<category-slug>/<title-slug>.pdf
```

Both the category and the title are slugified (lowercased, non-alphanumeric
characters collapsed to hyphens, title truncated to 80 characters) so file
and folder names are always filesystem-safe.

## Google Drive folder structure

On Drive, a top-level folder is created per **category** (matching the
keyword the article was scraped under, e.g. `pinjol`, `fintech`). The
exporter looks up an existing folder by name before creating a new one
(`get_or_create_folder`), so repeated runs reuse the same folder instead of
creating duplicates. Each article's PDF is uploaded into its category's
folder, and the folder id is cached in-process for the duration of a run.

## Idempotency

Before rendering or uploading anything, the exporter checks
`db.postgres.has_drive_url(article_id)`. If the article already has a
`drive_url` recorded, it's skipped entirely — so re-running
`python run_pipeline.py --step pdf` only uploads articles that don't have a
Drive backup yet.

## Authentication

Uses a Google Cloud **service account** JSON key (path configured via
`GOOGLE_DRIVE_CREDENTIALS_PATH`) with the `drive.file` scope, so no
interactive OAuth consent flow is needed — suitable for a headless batch
pipeline.
