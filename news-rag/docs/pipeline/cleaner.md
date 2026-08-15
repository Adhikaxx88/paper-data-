# Cleaner

`pipeline/cleaner.py`

## What it does

Loads every raw JSON file from `data/raw/`, normalizes the text fields, and
writes a single deduplicated, cleaned JSON file to `data/clean/`.

## Cleaning rules applied

1. **Strip HTML tags** — any `<...>` markup is removed.
2. **Remove special characters** — anything outside letters, digits,
   whitespace, and basic punctuation (`. , ! ? % -`) is stripped.
3. **Collapse whitespace** — repeated spaces/newlines/tabs are collapsed to a
   single space, and the result is trimmed.
4. **Normalize dates to ISO 8601** — the RFC-822 date from Google News (e.g.
   `Wed, 15 Aug 2026 09:00:00 GMT`) is parsed and converted to `YYYY-MM-DD`.
5. **Filter short articles** — any article whose cleaned `content` is
   shorter than `MIN_CONTENT_LENGTH` (default 100 characters) is dropped.
6. **Deduplicate by URL** — across all raw files combined, only the first
   occurrence of each URL is kept.

## Example: before vs after

**Before (raw):**

```json
{
  "source": "  <b>Kompas.com</b>  ",
  "title": "OJK Perketat Aturan  Pinjol!!",
  "content": "<p>Otoritas Jasa Keuangan   mengumumkan\n\naturan baru...</p>",
  "date": "Wed, 15 Aug 2026 09:00:00 GMT",
  "url": "https://www.kompas.com/...",
  "category": "pinjol"
}
```

**After (clean):**

```json
{
  "source": "Kompas.com",
  "title": "OJK Perketat Aturan Pinjol!!",
  "content": "Otoritas Jasa Keuangan mengumumkan aturan baru...",
  "date": "2026-08-15",
  "url": "https://www.kompas.com/...",
  "category": "pinjol"
}
```

## Output

- `data/clean/clean_<timestamp>.json`
