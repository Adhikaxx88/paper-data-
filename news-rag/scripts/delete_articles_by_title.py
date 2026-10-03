#!/usr/bin/env python3
"""Delete articles matching a title pattern from PostgreSQL + Qdrant.

Removes the clean_articles row (and its chunks via ON DELETE from chunks
referencing clean_articles.id), the matching raw_articles row, and the
Qdrant points carrying that article_id — keeping all three stores in sync.

Usage (run inside the backend container, or on the host with the .env
POSTGRES_HOST/QDRANT_URL pointed at the exposed ports):
    python scripts/delete_articles_by_title.py "%myanmar%meth%"
    python scripts/delete_articles_by_title.py "%myanmar%meth%" --yes
"""
import argparse
import sys
from pathlib import Path

import psycopg2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import POSTGRES_URL, QDRANT_URL, QDRANT_COLLECTION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern", help="SQL ILIKE pattern, e.g. '%%myanmar%%meth%%'")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, raw_id, title, url FROM clean_articles WHERE title ILIKE %s",
        (args.pattern,),
    )
    rows = cur.fetchall()

    if not rows:
        print(f"No clean_articles rows match {args.pattern!r}")
        cur.close()
        conn.close()
        return

    print(f"Matched {len(rows)} article(s):")
    for article_id, raw_id, title, url in rows:
        print(f"  {article_id}  {title}  ({url})")

    if not args.yes:
        confirm = input("Delete these from PostgreSQL + Qdrant? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            cur.close()
            conn.close()
            return

    for article_id, raw_id, title, _url in rows:
        r = requests.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete?wait=true",
            json={"filter": {"must": [{"key": "article_id", "match": {"value": str(article_id)}}]}},
        )
        r.raise_for_status()

        cur.execute("DELETE FROM chunks WHERE article_id = %s", (article_id,))
        cur.execute("DELETE FROM clean_articles WHERE id = %s", (article_id,))
        if raw_id:
            cur.execute("DELETE FROM raw_articles WHERE id = %s", (raw_id,))
        conn.commit()
        print(f"[{title[:60]}] deleted (qdrant + chunks + clean_articles + raw_articles)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
