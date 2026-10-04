"""Backfill payload "title" untuk point Qdrant pdf_knowledge yang title-nya kosong.

Sumber title yang benar adalah raw_articles.title di Postgres, dicocokkan lewat
payload "raw_id". Update memakai set_payload sehingga vector tidak tersentuh.

Default-nya dry-run: hanya mencetak rencana. Tambahkan --apply untuk menulis.

Dijalankan di dalam container backend (sudah punya psycopg2 & qdrant_client):
    docker exec -i news-rag-backend-1 python - [--apply] < scripts/backfill_pdf_titles.py
"""

import argparse
import os
from collections import defaultdict

import psycopg2
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, IsEmptyCondition, IsNullCondition, PayloadField

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6335")
COLLECTION = os.getenv("COLLECTION_NAME", "data-paper-child")
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "dbname": os.getenv("POSTGRES_DB"),
}
BATCH = 500


def missing_title_points(client: QdrantClient):
    """Yield (point_id, raw_id) untuk pdf_knowledge yang title-nya null/kosong/hilang."""
    flt = Filter(
        must=[FieldCondition(key="source_type", match={"value": "pdf_knowledge"})],
        should=[IsNullCondition(is_null=PayloadField(key="title")), IsEmptyCondition(is_empty=PayloadField(key="title"))],
    )
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=flt,
            limit=BATCH,
            offset=offset,
            with_payload=["raw_id", "filename"],
            with_vectors=False,
        )
        for p in points:
            yield p.id, p.payload.get("raw_id"), p.payload.get("filename")
        if offset is None:
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="tulis ke Qdrant (default: dry-run)")
    args = ap.parse_args()

    client = QdrantClient(url=QDRANT_URL)
    conn = psycopg2.connect(**DB_CONFIG)

    targets = list(missing_title_points(client))
    print(f"Point pdf_knowledge tanpa title: {len(targets)}")

    raw_ids = [r for _, r, _ in targets if r]
    titles = {}
    if raw_ids:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text, title FROM raw_articles WHERE id::text = ANY(%s)", (raw_ids,))
            titles = dict(cur.fetchall())

    plan = defaultdict(list)   # title -> [point_id]
    no_raw, no_title = [], []
    for pid, rid, fname in targets:
        if not rid:
            no_raw.append(pid)
            continue
        t = titles.get(rid)
        if not t:
            no_title.append((pid, rid, fname))
            continue
        plan[t].append(pid)

    total = sum(len(v) for v in plan.values())
    print(f"Akan diupdate : {total} point, dalam {len(plan)} title berbeda")
    print(f"Lewati (tanpa raw_id di payload): {len(no_raw)}")
    print(f"Lewati (raw_id tidak ada di raw_articles / title kosong): {len(no_title)}")

    print("\nSample 5 (before -> after):")
    shown = 0
    for pid, rid, fname in targets:
        if shown >= 5:
            break
        if rid in titles and titles[rid]:
            print(f"  point {pid}  file={fname}\n    before: title=<missing>\n    after : title={titles[rid]!r}")
            shown += 1

    if not args.apply:
        print("\nDRY-RUN: tidak ada yang ditulis. Jalankan ulang dengan --apply.")
        return

    updated = 0
    for title, ids in plan.items():
        for i in range(0, len(ids), BATCH):
            chunk = ids[i : i + BATCH]
            client.set_payload(collection_name=COLLECTION, payload={"title": title}, points=chunk, wait=True)
            updated += len(chunk)
    print(f"\nAPPLIED: {updated} point di-set_payload.")


if __name__ == "__main__":
    main()
