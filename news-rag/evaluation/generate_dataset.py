"""Generate a golden Q&A evaluation dataset from clean_articles via OpenRouter.

Pulls a source-diverse sample of articles from PostgreSQL, asks the
DATASET_GENERATOR_MODEL (served through OpenRouter) to write 2-3 Indonesian
question/answer pairs per article (mixing factual, practical, situational,
and statistical question types), and writes the result to
evaluation/golden_dataset_openrouter.csv.

Run with: docker compose run evaluation python evaluation/generate_dataset.py
"""
import argparse
import csv
import json
import re
import socket
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI, RateLimitError


def _postgres_hostname_resolves() -> bool:
    """Check whether the in-Docker "postgres" hostname is resolvable.

    Used to auto-detect whether this script is running inside the compose
    network (where service names resolve) or outside it (e.g. from a host
    Python/conda env on Windows), where they don't.
    """
    try:
        socket.gethostbyname("postgres")
        return True
    except socket.gaierror:
        return False


def _load_local_env() -> None:
    """Load evaluation/.env.local when running outside the Docker network.

    Triggered either by an explicit --local flag or by failing to resolve
    the "postgres" service hostname. Overrides POSTGRES_HOST/PORT,
    QDRANT_*, with localhost-mapped values matching the ports
    docker-compose.yml publishes to the host, before config.py reads them.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force loading evaluation/.env.local (localhost-mapped ports) "
        "instead of auto-detecting Docker networking.",
    )
    args, _ = parser.parse_known_args()

    if not (args.local or not _postgres_hostname_resolves()):
        return

    env_path = Path(__file__).parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        logger.info(f"Running outside Docker — loaded local overrides from {env_path}")
    elif args.local:
        print(f"warning: --local passed but {env_path} does not exist", file=sys.stderr)


_load_local_env()

from config import (  # noqa: E402
    DATASET_GENERATOR_MODEL,
    DATASET_GENERATOR_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    POSTGRES_URL,
    provider_body,
)

TARGET_TOTAL_QUESTIONS = 2500
MIN_CONTENT_LENGTH = 500
WARN_PAIRS_PER_ARTICLE = 4
EXCLUDED_CATEGORIES = {"additional"}
# Rate limiting: fixed delay between calls, plus exponential backoff on HTTP 429.
REQUEST_DELAY_SEC = 0.75
MAX_RETRIES = 4
BACKOFF_BASE_SEC = 2
# Separate file so the previous Ollama-generated golden_dataset.csv is kept
# for comparison until the new one is reviewed.
OUTPUT_PATH = Path(__file__).parent / "golden_dataset_openrouter.csv"

# Semua artikel (web_scraping + pdf_knowledge). topic_category dinormalisasi di SQL.
ALL_ARTICLES_QUERY = """
SELECT
    id,
    title,
    source,
    content,
    source_type,
    lower(replace(topic_category, '-', '_')) AS topic_category
FROM clean_articles
WHERE content IS NOT NULL
  AND LENGTH(content) > %s
  AND topic_category IS NOT NULL
  AND lower(topic_category) NOT IN ('additional')
ORDER BY topic_category, id
"""

GENERATION_PROMPT = """Buat tepat {n} pasang tanya-jawab Bahasa Indonesia dari artikel berikut, \
seperti pertanyaan orang tua tentang perkembangan anak atau kesehatan mental remaja.

Campurkan jenis pertanyaan: faktual ("Apa itu ..."), praktis ("Bagaimana cara ..."), \
situasional ("Kalau anak saya ..."), statistik ("Berapa persen ...").

Jawaban harus singkat (2-4 kalimat) dan hanya berdasarkan isi artikel, tanpa mengarang.

Judul: {title}

Artikel:
{content}

ATURAN OUTPUT (WAJIB DIIKUTI):
- Balas HANYA dengan JSON object berkunci "pairs" yang berisi array. Jangan tulis penjelasan, catatan, atau teks lain apa pun.
- Jangan gunakan markdown code fence (```).
- Format harus PERSIS seperti contoh ini:
{{"pairs": [{{"question": "Apa itu stunting?", "answer": "Stunting adalah kondisi gagal tumbuh pada anak akibat kekurangan gizi kronis."}}, {{"question": "Bagaimana cara mencegah stunting?", "answer": "Stunting dapat dicegah dengan pemenuhan gizi seimbang sejak masa kehamilan dan 1000 hari pertama kehidupan."}}]}}
"""

MAX_CONTENT_CHARS = 6000
RATE_LIMIT_HITS = {"429": 0, "retry": 0}


def fetch_articles() -> list[dict[str, Any]]:
    """Pull every usable clean_articles row (web_scraping and pdf_knowledge).

    Returns:
        List of dicts with id, title, source, content, source_type, topic_category
        (topic_category already normalized: lower() and "-" -> "_").
    """
    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(ALL_ARTICLES_QUERY, (MIN_CONTENT_LENGTH,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def allocate_questions(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign each article a number of Q&A pairs so the total is TARGET_TOTAL_QUESTIONS.

    Step 1: category quota = articles_in_category / total_articles * TARGET,
    rounded with the largest-remainder method so the quotas sum exactly to TARGET.
    Step 2: each category's quota is split across its articles as evenly as
    possible (base = quota // n, the first quota % n articles get one extra).

    Args:
        articles: Rows from fetch_articles(). Mutated: sets "n_pairs" on each.

    Returns:
        The same list, with "n_pairs" set on every article.
    """
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in articles:
        by_cat[a["topic_category"]].append(a)

    total = len(articles)
    exact = {c: len(v) / total * TARGET_TOTAL_QUESTIONS for c, v in by_cat.items()}
    quota = {c: int(e) for c, e in exact.items()}
    leftover = TARGET_TOTAL_QUESTIONS - sum(quota.values())
    for c in sorted(exact, key=lambda c: exact[c] - quota[c], reverse=True)[:leftover]:
        quota[c] += 1

    for c, members in by_cat.items():
        base, extra = divmod(quota[c], len(members))
        for i, a in enumerate(members):  # members already ordered by id
            a["n_pairs"] = base + (1 if i < extra else 0)
    return articles


def print_plan(articles: list[dict[str, Any]]) -> None:
    """Print the category/source distribution table, totals, and cost estimate."""
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for a in articles:
        key = (a["topic_category"], a["source_type"])
        s = stats.setdefault(key, {"articles": 0, "questions": 0})
        s["articles"] += 1
        s["questions"] += a["n_pairs"]

    print(f"{'kategori':32} {'source_type':14} {'artikel':>8} {'jatah_pertanyaan':>17} {'per_artikel':>12}")
    for (cat, src), s in sorted(stats.items(), key=lambda kv: -kv[1]["questions"]):
        per = s["questions"] / s["articles"]
        flag = "  <-- WARNING >4" if per > WARN_PAIRS_PER_ARTICLE else ""
        print(f"{cat:32} {src:14} {s['articles']:>8} {s['questions']:>17} {per:>12.2f}{flag}")
    total_q = sum(a["n_pairs"] for a in articles)
    print(f"\nTOTAL artikel: {len(articles)} | TOTAL pertanyaan: {total_q} | API calls: {len(articles)}")

    # Rough cost: ~4 chars/token for Indonesian, +~400 tokens prompt overhead per call,
    # ~60 output tokens per Q&A pair. gpt-4o-mini via OpenRouter: $0.15/M in, $0.60/M out.
    in_tokens = sum(min(len(a["content"]), 6000) / 4 + 400 for a in articles)
    out_tokens = total_q * 60
    cost = in_tokens / 1e6 * 0.15 + out_tokens / 1e6 * 0.60
    print(f"Estimasi token: input ~{in_tokens/1e6:.2f}M, output ~{out_tokens/1e6:.2f}M")
    print(f"Estimasi biaya kasar ({DATASET_GENERATOR_MODEL}): ~${cost:.2f} (perkiraan, bukan tagihan)")
    est_min = len(articles) * (REQUEST_DELAY_SEC + 2.5) / 60
    print(f"Estimasi durasi (tanpa retry 429): ~{est_min:.0f} menit")


def _normalize_pairs(pairs: Any) -> list[dict[str, str]]:
    """Coerce a parsed JSON value into a clean list of question/answer dicts.

    Handles both a bare list of {"question", "answer"} objects and a dict
    wrapping such a list under some key (e.g. {"qa_pairs": [...]}).
    """
    if isinstance(pairs, dict):
        # Model wrapped the array in an object, e.g. {"pairs": [...]}.
        list_values = [v for v in pairs.values() if isinstance(v, list)]
        pairs = list_values[0] if list_values else [pairs]

    if not isinstance(pairs, list):
        return []

    return [
        {"question": str(p["question"]).strip(), "answer": str(p["answer"]).strip()}
        for p in pairs
        if isinstance(p, dict) and p.get("question") and p.get("answer")
    ]


def _parse_qa_from_plain_text(text: str) -> list[dict[str, str]]:
    """Fallback extraction for plain-text "Q: ... A: ..." style output.

    Matches lines/blocks like "Q: ..." / "A: ..." or "1. Q: ... A: ...",
    tolerating optional numbering and either "Q"/"A" or the Indonesian
    "Pertanyaan"/"Jawaban" labels, case-insensitively.
    """
    pattern = re.compile(
        r"(?:^|\n)\s*(?:\d+[.)]\s*)?(?:Q|Pertanyaan)\s*[:.]\s*(?P<question>.+?)\s*\n+"
        r"\s*(?:\d+[.)]\s*)?(?:A|Jawaban)\s*[:.]\s*(?P<answer>.+?)"
        r"(?=\n\s*(?:\d+[.)]\s*)?(?:Q|Pertanyaan)\s*[:.]|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    pairs = [
        {"question": m.group("question").strip(), "answer": m.group("answer").strip()}
        for m in pattern.finditer(text)
    ]
    return [p for p in pairs if p["question"] and p["answer"]]


def parse_qa_pairs(raw_response: str) -> list[dict[str, str]]:
    """Extract a list of {question, answer} dicts from the model's raw output.

    Tries a direct JSON parse first, then strips markdown code fences and
    looks for the first JSON array/object in the text, and finally falls
    back to regex extraction of plain-text "Q: ... A: ..." style output for
    models that ignore the JSON-only instruction.

    Args:
        raw_response: The LLM's raw text output.

    Returns:
        List of dicts with "question" and "answer" keys, or [] if parsing fails.
    """
    text = raw_response.strip()

    try:
        return _normalize_pairs(json.loads(text))
    except json.JSONDecodeError:
        pass

    fenced = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    fenced = re.sub(r"```$", "", fenced).strip()

    match = re.search(r"[\[{].*[\]}]", fenced, flags=re.DOTALL)
    if match:
        try:
            pairs = _normalize_pairs(json.loads(match.group(0)))
            if pairs:
                return pairs
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON output, falling back to text extraction: {e}")

    return _parse_qa_from_plain_text(text)


def generate_qa_for_article(client: OpenAI, article: dict[str, Any]) -> list[dict[str, str]]:
    """Call the dataset generator model to produce Indonesian Q&A pairs for one article.

    Args:
        client: OpenAI-compatible client pointed at OpenRouter.
        article: Dict with title and content.

    Returns:
        List of {"question", "answer"} dicts, possibly empty on failure.
    """
    content = article["content"][:MAX_CONTENT_CHARS]
    prompt = GENERATION_PROMPT.format(n=article["n_pairs"], title=article["title"], content=content)

    raw = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=DATASET_GENERATOR_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"},
                extra_body=provider_body(DATASET_GENERATOR_PROVIDER),
            )
            raw = response.choices[0].message.content or ""
            break
        except RateLimitError as e:
            RATE_LIMIT_HITS["429"] += 1
            if attempt == MAX_RETRIES:
                logger.error(f"HTTP 429 persisted after {MAX_RETRIES} retries for article {article['id']}: {e}")
                return []
            wait = BACKOFF_BASE_SEC * (2 ** attempt)
            RATE_LIMIT_HITS["retry"] += 1
            logger.warning(f"HTTP 429 for article {article['id']}, retry {attempt + 1}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"LLM generation failed for article {article['id']}: {e}")
            return []

    pairs = parse_qa_pairs(raw)
    if not pairs:
        logger.warning(f"No valid Q&A pairs parsed for article {article['id']} ({article['title']!r})")
    # Keep exactly the requested count so the total matches TARGET_TOTAL_QUESTIONS.
    return pairs[: article["n_pairs"]]


def build_dataset(client: OpenAI, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate Q&A rows for every sampled article.

    Args:
        client: OpenAI-compatible client pointed at OpenRouter.
        articles: Sampled article dicts from fetch_sample_articles().

    Returns:
        List of row dicts ready to write to CSV.
    """
    rows = []
    failed_articles = 0
    short_articles = 0
    for i, article in enumerate(articles, start=1):
        logger.info(f"[{i}/{len(articles)}] ({article['topic_category']}, n={article['n_pairs']}) {article['title']!r}")
        pairs = generate_qa_for_article(client, article)
        if not pairs:
            failed_articles += 1
        elif len(pairs) < article["n_pairs"]:
            short_articles += 1
        for pair in pairs:
            rows.append(
                {
                    "question": pair["question"],
                    "ground_truth": pair["answer"],
                    "article_id": article["id"],
                    "source_title": article["title"],
                    "source": article["source"],
                    "topic_category": article["topic_category"],
                    "source_type": article["source_type"],
                    "dataset_model": DATASET_GENERATOR_MODEL,
                    "dataset_provider": DATASET_GENERATOR_PROVIDER,
                }
            )
        time.sleep(REQUEST_DELAY_SEC)
    logger.info(f"Articles with zero parsed pairs: {failed_articles}/{len(articles)}")
    logger.info(f"Articles with fewer pairs than requested: {short_articles}/{len(articles)}")
    logger.info(f"HTTP 429 hits: {RATE_LIMIT_HITS['429']}, retries: {RATE_LIMIT_HITS['retry']}")
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write generated rows to a CSV file.

    Args:
        rows: Row dicts with question, ground_truth, article_id, source_title, source.
        path: Destination CSV path.
    """
    fieldnames = [
        "question",
        "ground_truth",
        "article_id",
        "source_title",
        "source",
        "topic_category",
        "source_type",
        "dataset_model",
        "dataset_provider",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-only", action="store_true", help="print distribution and cost estimate, no API calls")
    args, _ = parser.parse_known_args()

    articles = allocate_questions(fetch_articles())
    logger.info(f"Loaded {len(articles)} articles (web_scraping + pdf_knowledge, content > {MIN_CONTENT_LENGTH} chars)")
    if not articles:
        logger.warning("No articles found matching criteria; nothing to generate")
        return

    print_plan(articles)
    over = {a["topic_category"] for a in articles if a["n_pairs"] > WARN_PAIRS_PER_ARTICLE}
    if over:
        logger.warning(f"Categories with more than {WARN_PAIRS_PER_ARTICLE} pairs/article: {sorted(over)}")
    if args.plan_only:
        print("\n--plan-only: tidak ada panggilan API.")
        return

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL, max_retries=0)
    rows = build_dataset(client, articles)

    write_csv(rows, OUTPUT_PATH)
    logger.info(f"Wrote {len(rows)} Q&A pairs from {len(articles)} articles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
