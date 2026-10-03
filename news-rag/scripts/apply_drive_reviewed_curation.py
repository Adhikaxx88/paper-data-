#!/usr/bin/env python3
"""Apply the human-verified KEEP/DELETE decisions for drive_reviewed articles.

Decisions were made by web-researching each of the 25 drive_reviewed
articles' cleaned titles and confirming source+url+date, then reviewed and
confirmed by the user — hardcoded here rather than re-derived, since this is
a one-off application of an already-approved list, not a fresh heuristic run.

Order per article:
  DELETE: remove matching Qdrant chunks first (by their current
          drive_reviewed:// url), then delete the Postgres row. If Qdrant
          delete fails, the Postgres row is untouched and the article is
          simply retried later — the reverse order would risk an orphaned
          Qdrant chunk with no Postgres row to track it for retry.
  KEEP:   read the row's CURRENT url from Postgres first (still the old
          drive_reviewed://<title>.pdf value at this point), use that to
          find its Qdrant chunks, merge the new source/date into their
          payload via POST (verified earlier: PUT wipes chunk_text/title;
          PATCH 404s), then update the Postgres row's source/published/url.

Run from inside the backend container so config.py's POSTGRES_URL/QDRANT_URL
resolve to the real news-rag instances, not the other Qdrant project running
on this host's port 6333.
"""
import sys
from pathlib import Path

import psycopg2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import POSTGRES_URL, QDRANT_URL, QDRANT_COLLECTION

DELETE_IDS = [
    "39c795fb-14d9-414a-8959-6d6b4cbf49f1",
    "4f3180ca-19da-4b11-ad15-b5b3b764fb00",
    "698b7951-7be6-4ef8-92d7-b19390ae9141",
    "7b62a111-ba9e-4ff9-bf98-40ac31f7625a",
    "7c3d7fe9-eb79-4b9a-83a8-be5e54fddf4e",
    "8549e977-a4e8-4681-80bc-a8d6af1a1b2b",
    "857f6bd4-2d5c-450c-a972-5ceec21d798f",
    "8b00f4dd-99e2-45f5-9c51-204145137129",
    "9ccab4da-bd90-4f16-9c67-dcf591e91218",
    "abed6305-14ef-4b86-9981-3b6b4462fb22",
    "e5b4c8f2-75e3-46ad-83f6-2122b57361b2",
    "f8048001-90cb-4ce0-ba69-4b0d7dd13fc7",
]

# id -> (source, date YYYY-MM-DD, canonical url)
#
# NOTE: the original 13 KEEP rows included 3 that turned out to be exact
# duplicates of already-scraped articles (their canonical URL already
# existed under a different id, and their own PDF content literally embeds
# "Source ... Published ... URL ..." matching that existing row) — those 3
# were removed via remove_drive_reviewed_duplicates.py instead of merged
# here. This dict now holds only the remaining 10 genuinely-new articles.
KEEP_ROWS = {
    "1e8f8ae8-3923-4042-b079-57e67f879537": (
        "The Conversation", "2023-01-02",
        "https://theconversation.com/data-bicara-meski-sepertiga-remaja-punya-masalah-kesehatan-mental-hanya-4-3-orang-tua-mendeteksi-anak-mereka-butuh-bantuan-196596",
    ),
    "323024c3-366b-45f7-ba36-b40aece42512": (
        "Medium", "2025-10-09",
        "https://medium.com/@daffaghiffarykusuma/dampak-stres-kerja-di-indonesia-data-biaya-dan-solusi-2024-2025-e4d6262f49c5",
    ),
    "37877df8-67a7-476b-b340-fde69c4c0b7c": (
        "GoodStats", "2025-10-27",
        "https://goodstats.id/article/data-depresi-dan-bunuh-diri-Xs9cn",
    ),
    "5e34fa56-51a2-4c77-abcd-8e54a759da6d": (
        "Cakaplah.com", "2025-09-16",
        "https://www.cakaplah.com/berita/baca/127701/2025/09/16/dipicu-medsos-kasus-gangguan-mental-remaja-naik-30-persen-tiap-tahun",
    ),
    "9a82754e-23b7-4a2f-9d8b-b220d3ca156c": (
        "NPR", "2026-06-15",
        "https://www.npr.org/2026/06/15/nx-s1-5858644/britain-social-media-ban",
    ),
    "9ea0e730-acaf-44e0-ba4b-3f864d30ad23": (
        "GoodStats", "2024-10-13",
        "https://data.goodstats.id/statistic/pengaruh-tiktok-terhadap-kesehatan-mental-remaja-0RVC0",
    ),
    "aa7fc7b4-ad2a-43b0-ab7e-815d3aae7f8e": (
        "Kompasiana.com", "2024-12-06",
        "https://www.kompasiana.com/tiorida0559/6752c487ed64150d0a249072/media-sosial-dan-dampaknya-bagi-kesehatan-menta-gen-z",
    ),
    "b8b62d62-877b-48d9-b7d6-4addd9188383": (
        "Kompas.com", "2025-02-02",
        "https://nasional.kompas.com/read/2025/02/02/15215161/banyak-anak-indonesia-alami-gangguan-mental-karena-media-sosial",
    ),
    "dd51dd81-7a6f-4d74-918c-1d904f654bcc": (
        "Reuters", "2026-08-24",
        "https://www.freemalaysiatoday.com/category/world/2026/08/24/from-australia-to-europe-countries-move-to-curb-children-s-social-media-access",
    ),
    "f849f9cf-9bcb-455a-95fa-d91469ede179": (
        "Associated Press", "2026-03-27",
        "https://www.local10.com/business/2026/03/27/in-the-wake-of-us-social-media-verdicts-a-look-at-what-limits-other-countries-have-imposed-for-kids/",
    ),
}


def qdrant_scroll_ids_by_url(url_val):
    body = {
        "filter": {"must": [{"key": "url", "match": {"value": url_val}}]},
        "limit": 200,
        "with_payload": False,
        "with_vector": False,
    }
    r = requests.post(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll", json=body)
    r.raise_for_status()
    return [p["id"] for p in r.json()["result"]["points"]]


def qdrant_delete_by_url(url_val):
    r = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete?wait=true",
        json={"filter": {"must": [{"key": "url", "match": {"value": url_val}}]}},
    )
    r.raise_for_status()
    return r.json()


def qdrant_merge_payload(point_ids, payload_patch):
    if not point_ids:
        return
    r = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/payload?wait=true",
        json={"payload": payload_patch, "points": point_ids},
    )
    r.raise_for_status()


def main():
    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()

    print(f"=== DELETE: {len(DELETE_IDS)} articles ===")
    for id_ in DELETE_IDS:
        cur.execute("SELECT title, url FROM clean_articles WHERE id = %s", (id_,))
        row = cur.fetchone()
        if row is None:
            print(f"  {id_}: not found in clean_articles, skipping")
            continue
        title, url = row
        before_ids = qdrant_scroll_ids_by_url(url)
        qdrant_delete_by_url(url)
        cur.execute("DELETE FROM clean_articles WHERE id = %s", (id_,))
        conn.commit()
        print(f"  [{title[:50]}] qdrant chunks deleted: {len(before_ids)}, postgres row deleted")

    print(f"\n=== KEEP: {len(KEEP_ROWS)} articles ===")
    for id_, (source, date, url) in KEEP_ROWS.items():
        cur.execute("SELECT title, url FROM clean_articles WHERE id = %s", (id_,))
        row = cur.fetchone()
        if row is None:
            print(f"  {id_}: not found in clean_articles, skipping")
            continue
        title, old_url = row

        point_ids = qdrant_scroll_ids_by_url(old_url)
        if not point_ids:
            # Fallback: the synthetic url may not exactly match if content
            # changed since the last scan; try the current DB url too.
            point_ids = qdrant_scroll_ids_by_url(url)

        qdrant_merge_payload(point_ids, {"source": source, "date": date})

        cur.execute(
            "UPDATE clean_articles SET source = %s, published = %s::date, url = %s WHERE id = %s",
            (source, date, url, id_),
        )
        conn.commit()
        print(f"  [{title[:50]}] qdrant chunks updated: {len(point_ids)}, postgres row updated -> {source} / {date}")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
