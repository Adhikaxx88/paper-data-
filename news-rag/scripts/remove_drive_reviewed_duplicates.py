#!/usr/bin/env python3
"""Remove 3 drive_reviewed rows discovered to be exact duplicates of
already-scraped articles (their canonical URL already existed in
clean_articles under a different id, and their own extracted PDF content
literally contains "Source ... Published ... URL ..." matching that
existing row — confirming these are re-uploaded PDF exports of articles the
pipeline had already correctly scraped, not new content).
"""
import sys
from pathlib import Path

import psycopg2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import POSTGRES_URL, QDRANT_URL, QDRANT_COLLECTION

DUPLICATE_IDS = [
    "0a8a4de9-c06e-4a06-8a45-b39e298d4d77",
    "30a91f73-3d5b-46af-b805-61ce2112aa8f",
    "d0b5d04e-d7e3-49e2-a7f1-73a2aa76033e",
]


def main():
    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()

    for id_ in DUPLICATE_IDS:
        cur.execute("SELECT title, url FROM clean_articles WHERE id = %s", (id_,))
        row = cur.fetchone()
        if row is None:
            print(f"{id_}: not found, skip")
            continue
        title, url = row
        r = requests.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete?wait=true",
            json={"filter": {"must": [{"key": "url", "match": {"value": url}}]}},
        )
        r.raise_for_status()
        cur.execute("DELETE FROM clean_articles WHERE id = %s", (id_,))
        conn.commit()
        print(f"[{title[:50]}] duplicate removed (qdrant + postgres)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
