#!/usr/bin/env python3
"""Backfill source + date for drive_reviewed articles by parsing filename/content.

Run from inside the backend/pipeline container (or anywhere config.py's
POSTGRES_URL/QDRANT_URL resolve correctly) — never with hardcoded connection
details, since this project runs two separate Qdrant instances on this
machine and a wrong host/port silently talks to the other one.

Usage:
    python scripts/backfill_drive_reviewed.py            # preview only, no writes
    python scripts/backfill_drive_reviewed.py --apply     # actually update PG + Qdrant
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import POSTGRES_URL, QDRANT_URL, QDRANT_COLLECTION

DOMAIN_MAP = {
    "databoks.katadata.co.id": "Databoks Katadata",
    "katadata.co.id": "Katadata",
    "goodstats.id": "GoodStats",
    "kompasiana.com": "Kompasiana.com",
    "kompas.id": "Kompas.id",
    "kompas.com": "Kompas.com",
    "tempo.co": "Tempo.co",
    "detik.com": "Detik.com",
    "antara.news": "Antara News",
    "antaranews.com": "Antara News",
    "timesindonesia.co.id": "Times Indonesia",
    "prohealth.id": "Prohealth",
    "medium.com": "Medium",
    "bnn.go.id": "BNN",
    "kemkes.go.id": "Kemkes",
    "asianewsnet.net": "Asia News Network",
    "vietnam.vn": "Vietnam.vn",
}

SOURCE_KEYWORDS = {
    "goodstats": "GoodStats",
    "kompasiana": "Kompasiana.com",
    "kompas id": "Kompas.id",
    "tempo co": "Tempo.co",
    "detikco": "Detik.com",
    "antara news": "Antara News",
    "times indonesia": "Times Indonesia",
    "prohealth": "Prohealth",
    "medium": "Medium",
    "katadata": "Databoks Katadata",
    "databoks": "Databoks Katadata",
    "asia news ne": "Asia News Network",
}

MONTHS_ID = {
    "januari": "01", "februari": "02", "maret": "03", "april": "04", "mei": "05",
    "juni": "06", "juli": "07", "agustus": "08", "september": "09",
    "oktober": "10", "november": "11", "desember": "12",
}
MONTHS_EN = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def extract_source_from_title(title):
    t = title.lower()
    for kw, name in SOURCE_KEYWORDS.items():
        if kw in t:
            return name
    return None


def extract_urls_from_content(content):
    urls = re.findall(r"https?://[^\s\)\]\>\"\']+", content or "")
    partial = re.findall(r"https? ([a-z0-9\-\.]+\.[a-z]{2,}[^\s]*)", content or "")
    urls += ["https://" + u.replace(" ", "") for u in partial]
    return urls


def extract_source_from_urls(urls):
    for url in urls:
        try:
            domain = urlparse(url).netloc.lower().lstrip("www.")
            for key, name in DOMAIN_MAP.items():
                if key in domain:
                    return name, url
        except Exception:
            pass
    return None, None


def extract_date_from_urls(urls):
    for url in urls:
        m = re.search(r"/(20\d{2})[/-](\d{2})[/-](\d{2})/", url)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.search(r"/(20\d{2})[/-](\d{2})/", url)
        if m:
            return f"{m.group(1)}-{m.group(2)}-01"
    return None


def extract_date_from_content(content):
    if not content:
        return None
    c = content.lower()
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS_ID) + r")\s+(20\d{2})", c)
    if m:
        return f"{m.group(3)}-{MONTHS_ID[m.group(2)]}-{int(m.group(1)):02d}"
    m = re.search(r"(" + "|".join(MONTHS_ID) + r")\s+(20\d{2})", c)
    if m:
        return f"{m.group(2)}-{MONTHS_ID[m.group(1)]}-01"
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS_EN) + r"),?\s+(20\d{2})", c)
    if m:
        return f"{m.group(3)}-{MONTHS_EN[m.group(2)]}-{int(m.group(1)):02d}"
    m = re.search(r"(" + "|".join(MONTHS_EN) + r"),?\s+(20\d{2})", c)
    if m:
        return f"{m.group(2)}-{MONTHS_EN[m.group(1)]}-01"
    m = re.search(r"(20\d{2})-(0[1-9]|1[0-2])-(\d{2})", content)
    if m:
        return m.group(0)
    return None


def qdrant_update_by_url(url_val, payload_patch):
    """Merge payload_patch into every chunk whose payload.url matches url_val.

    Uses POST (merge) rather than PUT (full overwrite) — PUT on this
    endpoint replaces the ENTIRE payload with just payload_patch, destroying
    chunk_text/title/url on every matched point. Verified against a
    disposable Qdrant collection before this script ever touched real data.
    """
    body = {
        "filter": {"must": [{"key": "url", "match": {"value": url_val}}]},
        "limit": 200,
        "with_payload": False,
        "with_vector": False,
    }
    r = requests.post(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll", json=body)
    r.raise_for_status()
    points = r.json().get("result", {}).get("points", [])
    if not points:
        return 0
    ids = [p["id"] for p in points]
    r = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/payload",
        json={"payload": payload_patch, "points": ids},
    )
    r.raise_for_status()
    return len(ids)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="Write changes to PostgreSQL + Qdrant (default: preview only)"
    )
    args = parser.parse_args()

    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, url FROM clean_articles WHERE source = 'drive_reviewed'")
    rows = cur.fetchall()
    print(f"Found {len(rows)} drive_reviewed articles\n")

    results = []
    for id_, title, content, pg_url in rows:
        src = extract_source_from_title(title)
        urls = extract_urls_from_content(content)
        url_src, canonical_url = extract_source_from_urls(urls)
        src = src or url_src
        date = extract_date_from_urls(urls) or extract_date_from_content(content)

        results.append((id_, title, src, date, canonical_url or pg_url))
        print(f"[{title[:55]}]")
        print(f"  source : {src or 'UNKNOWN'}")
        print(f"  date   : {date or 'NOT FOUND'}")
        print(f"  url    : {canonical_url or pg_url}")
        print()

    print("\n─── PREVIEW ───────────────────────────────────────────────────")
    unknown_count = 0
    no_date_count = 0
    for id_, title, src, date, url in results:
        print(f"{title[:45]:<45} | {(src or 'UNKNOWN'):<25} | {date or 'NO DATE'}")
        if not src:
            unknown_count += 1
        if not date:
            no_date_count += 1
    print(f"\n{unknown_count}/{len(results)} UNKNOWN source, {no_date_count}/{len(results)} NO DATE")

    if not args.apply:
        print("\nPreview only (pass --apply to write). No changes made.")
        cur.close()
        conn.close()
        return

    qdrant_total = 0
    for id_, title, src, date, url in results:
        cur.execute(
            """
            UPDATE clean_articles
            SET source    = COALESCE(%s, source),
                published = COALESCE(%s::date, published),
                url       = COALESCE(%s, url)
            WHERE id = %s
            """,
            (src, date, url, id_),
        )

        if url:
            patch = {}
            if src:
                patch["source"] = src
            if date:
                patch["date"] = date
            if patch:
                n = qdrant_update_by_url(url, patch)
                if n == 0:
                    drive_url = f"drive_reviewed://{title}.pdf"
                    n = qdrant_update_by_url(drive_url, patch)
                qdrant_total += n
                print(f"  Qdrant: {n} chunks updated for [{title[:40]}]")

    conn.commit()
    print(f"\nPostgreSQL: {len(results)} rows updated (COALESCE — existing values kept where already set)")
    print(f"Qdrant:     {qdrant_total} chunks updated (merged via POST — other payload fields untouched)")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
