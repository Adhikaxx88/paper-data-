#!/usr/bin/env python3
"""Backfill the Qdrant payload's `url` field for the 10 KEEP articles from
the first drive_reviewed batch — apply_drive_reviewed_curation.py's payload
merge only included source/date, leaving url at its old drive_reviewed://
placeholder. Surfaced by adding clickable source links in the frontend,
which needs a real http(s) url to render a link.
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import QDRANT_URL, QDRANT_COLLECTION

# article_id -> canonical url (same values already written to clean_articles.url)
URLS = {
    "1e8f8ae8-3923-4042-b079-57e67f879537": "https://theconversation.com/data-bicara-meski-sepertiga-remaja-punya-masalah-kesehatan-mental-hanya-4-3-orang-tua-mendeteksi-anak-mereka-butuh-bantuan-196596",
    "323024c3-366b-45f7-ba36-b40aece42512": "https://medium.com/@daffaghiffarykusuma/dampak-stres-kerja-di-indonesia-data-biaya-dan-solusi-2024-2025-e4d6262f49c5",
    "37877df8-67a7-476b-b340-fde69c4c0b7c": "https://goodstats.id/article/data-depresi-dan-bunuh-diri-Xs9cn",
    "5e34fa56-51a2-4c77-abcd-8e54a759da6d": "https://www.cakaplah.com/berita/baca/127701/2025/09/16/dipicu-medsos-kasus-gangguan-mental-remaja-naik-30-persen-tiap-tahun",
    "9a82754e-23b7-4a2f-9d8b-b220d3ca156c": "https://www.npr.org/2026/06/15/nx-s1-5858644/britain-social-media-ban",
    "9ea0e730-acaf-44e0-ba4b-3f864d30ad23": "https://data.goodstats.id/statistic/pengaruh-tiktok-terhadap-kesehatan-mental-remaja-0RVC0",
    "aa7fc7b4-ad2a-43b0-ab7e-815d3aae7f8e": "https://www.kompasiana.com/tiorida0559/6752c487ed64150d0a249072/media-sosial-dan-dampaknya-bagi-kesehatan-menta-gen-z",
    "b8b62d62-877b-48d9-b7d6-4addd9188383": "https://nasional.kompas.com/read/2025/02/02/15215161/banyak-anak-indonesia-alami-gangguan-mental-karena-media-sosial",
    "dd51dd81-7a6f-4d74-918c-1d904f654bcc": "https://www.freemalaysiatoday.com/category/world/2026/08/24/from-australia-to-europe-countries-move-to-curb-children-s-social-media-access",
    "f849f9cf-9bcb-455a-95fa-d91469ede179": "https://www.local10.com/business/2026/03/27/in-the-wake-of-us-social-media-verdicts-a-look-at-what-limits-other-countries-have-imposed-for-kids/",
}


def scroll_ids_by_article_id(article_id):
    body = {
        "filter": {"must": [{"key": "article_id", "match": {"value": article_id}}]},
        "limit": 200,
        "with_payload": False,
        "with_vector": False,
    }
    r = requests.post(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll", json=body)
    r.raise_for_status()
    return [p["id"] for p in r.json()["result"]["points"]]


def merge_payload(point_ids, patch):
    if not point_ids:
        return
    r = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/payload?wait=true",
        json={"payload": patch, "points": point_ids},
    )
    r.raise_for_status()


def main():
    for article_id, url in URLS.items():
        ids = scroll_ids_by_article_id(article_id)
        merge_payload(ids, {"url": url})
        print(f"{article_id}: {len(ids)} chunks -> url set")


if __name__ == "__main__":
    main()
