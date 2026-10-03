#!/usr/bin/env python3
"""Apply KEEP/DELETE decisions for the 34 orphaned drive_reviewed articles
discovered in Qdrant with zero backing rows in clean_articles (they reached
Qdrant via a path that bypassed the normal raw_articles -> clean_articles ->
embed pipeline). Since the live serving path (rag/retriever.py) reads
title/source/date/url straight from the Qdrant payload and never consults
clean_articles at query time, fixing the Qdrant payload is what actually
matters here — there is no Postgres row to update or delete for either list.

Matched by article_id (not url) since these chunks have no Postgres row to
read an old canonical url from, unlike the first 25-article batch.
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import QDRANT_URL, QDRANT_COLLECTION

DELETE_ARTICLE_IDS = [
    "0965de30-d9cc-4e14-beb3-e74f35f91289",
    "7a16e6d9-1cc8-4580-b53b-c3e687fa53f4",
    "5e3f4a25-2540-41a2-9fed-f9ade04f6635",
    "148aa99e-5b9c-471f-b78d-9bd349bdf979",
    "a19443b8-765e-4e36-90db-e85945ddd13e",
    "a025aaa3-0b74-4684-8adc-a5ac1c788724",
    "bb6f57d7-04c2-4501-8205-7f9e4ecddf70",
    "5975867e-8c69-4c06-9c65-021a02964157",
    "9db4c8fb-0900-4f4f-956d-1e461ca3d35a",
    "81cbb92f-6fb3-4a9a-ad14-ba3694fe28cc",
    "ac970c1e-6643-447a-8866-6b1686a40217",
    "7d280534-7a1d-4e9f-9911-8a439cf7e883",
    "eb611f8e-3f6e-495f-83f2-f6f3583683ec",
    "04fae17a-3236-4a91-8336-6d22382599b7",
    "15907ae3-b4f5-483e-b494-1881ecaf55aa",
    "2eaac8eb-faca-44fd-888d-3be78ce077d3",
    "508d6cf4-b3b1-4357-9bf3-a9836a853637",
    "fe6a99c7-4459-4f55-8f7d-3427ecdbe3b1",  # duplicate of cc237662, keeping cc237662 instead
]

# article_id -> (title, source, date, url)
KEEP_ROWS = {
    "0fc5eebe-bc1d-4f10-ac11-faebc3041f60": (
        "School based drug prevention in Saudi Arabia: are physical education teachers prepared?",
        "Frontiers in Public Health", "2026-08-19",
        "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2026.1911155/full",
    ),
    "5aefac3a-e285-4250-9972-3c50f7fb6b77": (
        "2026/22 \"Playing to Earn: Indonesia's Gold Farmers in World of Warcraft Classic\" by Brandon Tan Jun Wen",
        "ISEAS – Yusof Ishak Institute", "2026-04-01",
        "https://www.iseas.edu.sg/articles-commentaries/iseas-perspective/2026-22-playing-to-earn-indonesias-gold-farmers-in-world-of-warcraft-classic-by-brandon-tan-jun-wen/",
    ),
    "df7d1426-2574-482b-82c2-cf412ce98897": (
        "Digital communication symbols and intergenerational gap: a case study analysis",
        "Frontiers in Sociology", "2026-03-19",
        "https://www.frontiersin.org/journals/sociology/articles/10.3389/fsoc.2026.1633629/full",
    ),
    "92397911-4051-4855-adb4-ed0452e28b7e": (
        "Digital marketing of e-cigarettes in Southeast Asia: a neglected digital health issue",
        "Frontiers in Digital Health", "2026-06-04",
        "https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2026.1790973/full",
    ),
    "60bc013c-c47b-40f1-995e-e35257d3a80d": (
        "Gaming platform Roblox has finally cracked how to enforce age verification for kids",
        "Republic World", "2026-04-30",
        "https://www.republicworld.com/tech/gaming-platform-roblox-has-finally-cracked-how-to-enforce-age-verification-for-kids",
    ),
    "cc237662-ee27-458a-ad1b-cdd9bb6d68d0": (
        "Google.org & YouTube commit $20M to teen digital wellbeing with open source curriculum",
        "YouTube Blog", "2026-03-12",
        "https://blog.youtube/news-and-events/google-youtube-funding-digital-wellbeing-summit/",
    ),
    "7d905313-0559-4104-a2e9-48dd51ae5136": (
        "Indonesia becomes first in Southeast Asia to ban social media for kids",
        "Azernews", "2026-03-29",
        "https://www.azernews.az/region/256300.html",
    ),
    "f6e970c0-10e1-42c9-bc6d-1e789a3c1689": (
        "Australia plans to strengthen laws banning children from social media",
        "NPR", "2026-06-26",
        "https://www.npr.org/2026/06/26/g-s1-130375/australia-plans-to-strengthen-laws-banning-children-from-social-media",
    ),
    "fd365834-34c8-4e19-9fb6-8a4866f8524d": (
        "Indonesia bolsters social rehabilitation in deradicalization drive",
        "Antara News", "2026-07-27",
        "https://en.antaranews.com/news/424196/indonesia-bolsters-social-rehabilitation-in-deradicalization-drive",
    ),
    "13f4da8e-4b0a-4fee-bd26-1993580d7733": (
        "Another Malaysian nabbed trying to smuggle drugs into Indonesia",
        "The Star", "2026-08-04",
        "https://www.thestar.com.my/news/nation/2026/08/04/another-malaysian-nabbed-trying-to-smuggle-drugs-into-indonesia",
    ),
    "25741423-7ec3-45c8-97b1-aa73707d860b": (
        "UK sets strict screen time rules for kids: global push to protect children",
        "U.S. News & World Report", "2026-03-27",
        "https://www.usnews.com/news/world/articles/2026-03-27/uk-joins-global-push-to-rein-in-childrens-screen-use-with-national-guidance",
    ),
    "f2e77f1a-a092-4de9-8135-ca0ecea84877": (
        "Indonesia arrests 10 Myanmar nationals following liquid meth bust",
        "New Straits Times", "2026-08-21",
        "https://www.nst.com.my/amp/world/region/2026/08/1516279/indonesia-arrests-10-myanmar-nationals-following-liquid-meth-bust",
    ),
    "e32a7176-97e0-4858-a017-627c600eb546": (
        "Roblox announces control measures to comply with Indonesia's social media curb",
        "The Jakarta Post", "2026-05-01",
        "https://www.thejakartapost.com/indonesia/2026/05/01/roblox-announces-control-measures-to-comply-with-indonesias-social-media-curb",
    ),
    "f04a8b45-c6ac-45ad-9db4-780bfcce9751": (
        "Teen among eight nabbed in Johor drug raids over 60kg of meth seized",
        "The Star", "2026-07-22",
        "https://www.thestar.com.my/news/nation/2026/07/22/teen-among-eight-nabbed-in-johor-drug-raids-over-60kg-of-meth-seized",
    ),
    "312352c2-374c-49de-a7b1-dc19c813abd6": (
        "Indonesia rolls out social media ban for under-16s",
        "Tempo.co English", "2026-03-28",
        "https://en.tempo.co/read/2095038/indonesia-rolls-out-social-media-ban-for-under-16s",
    ),
    "8c5e8562-da1c-4f07-82de-de0035ba30d0": (
        "Indonesia warns Meta, Google over youth social media",
        "News.az", "2026-03-31",
        "https://news.az/news/indonesia-warns-meta-google-over-youth-social-media",
    ),
}


def qdrant_delete_by_article_id(article_id):
    r = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete?wait=true",
        json={"filter": {"must": [{"key": "article_id", "match": {"value": article_id}}]}},
    )
    r.raise_for_status()
    return r.json()


def qdrant_scroll_ids_by_article_id(article_id):
    body = {
        "filter": {"must": [{"key": "article_id", "match": {"value": article_id}}]},
        "limit": 200,
        "with_payload": False,
        "with_vector": False,
    }
    r = requests.post(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll", json=body)
    r.raise_for_status()
    return [p["id"] for p in r.json()["result"]["points"]]


def qdrant_merge_payload(point_ids, payload_patch):
    if not point_ids:
        return
    r = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/payload?wait=true",
        json={"payload": payload_patch, "points": point_ids},
    )
    r.raise_for_status()


def main():
    print(f"=== DELETE: {len(DELETE_ARTICLE_IDS)} orphaned articles ===")
    for aid in DELETE_ARTICLE_IDS:
        ids = qdrant_scroll_ids_by_article_id(aid)
        qdrant_delete_by_article_id(aid)
        print(f"  {aid}: {len(ids)} chunks deleted")

    print(f"\n=== KEEP: {len(KEEP_ROWS)} orphaned articles ===")
    for aid, (title, source, date, url) in KEEP_ROWS.items():
        point_ids = qdrant_scroll_ids_by_article_id(aid)
        qdrant_merge_payload(point_ids, {"title": title, "source": source, "date": date, "url": url})
        print(f"  {aid}: {len(point_ids)} chunks updated -> {source} / {date}")

    print("\nDone. (No Postgres changes — these articles have no clean_articles row; "
          "the live serving path reads title/source/date/url from Qdrant payload directly.)")


if __name__ == "__main__":
    main()
