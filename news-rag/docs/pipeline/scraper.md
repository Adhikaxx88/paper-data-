# Scraper

`pipeline/scraper.py`

## What it does

Scrapes Google News for each keyword configured in `NEWS_KEYWORDS` using the
[`gnews`](https://pypi.org/project/gnews/) library, fetches the full article
text for each result, and saves the combined output as a timestamped JSON
file in `data/raw/`.

## Inputs

- `NEWS_KEYWORDS` (from `.env`): comma-separated list of search terms. Each
  keyword doubles as the article's `category`.
- `ARTICLES_PER_KEYWORD` (in `config.py`): max results fetched per keyword
  (default 20).

## Outputs

- `data/raw/scrape_<timestamp>.json`: a JSON array of article dicts.

## Deduplication

Before scraping, the scraper loads every URL already present in
`data/raw/*.json` and skips any result whose URL was seen before — across the
entire history of raw files, not just the current run. This makes repeated
runs of `python run_pipeline.py --step scrape` only fetch genuinely new
articles.

## Example output JSON structure

```json
[
  {
    "source": "Kompas.com",
    "title": "OJK Perketat Aturan Pinjol",
    "content": "Otoritas Jasa Keuangan mengumumkan aturan baru...",
    "date": "Wed, 15 Aug 2026 09:00:00 GMT",
    "url": "https://www.kompas.com/...",
    "category": "pinjol"
  }
]
```

Note that `date` is still in the raw RFC-822 format returned by Google News
at this stage — it is normalized to ISO 8601 by the [cleaner](cleaner.md).
