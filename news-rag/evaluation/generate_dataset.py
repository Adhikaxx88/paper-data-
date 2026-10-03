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
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI


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

ARTICLES_PER_SOURCE = 5
MAX_ARTICLES_TOTAL = 50
MIN_CONTENT_LENGTH = 500
QA_PAIRS_PER_ARTICLE = "2-3"
# Separate file so the previous Ollama-generated golden_dataset.csv is kept
# for comparison until the new one is reviewed.
OUTPUT_PATH = Path(__file__).parent / "golden_dataset_openrouter.csv"

SAMPLE_QUERY = """
WITH ranked AS (
    SELECT
        id,
        title,
        source,
        content,
        ROW_NUMBER() OVER (
            PARTITION BY source ORDER BY LENGTH(content) DESC
        ) AS rn
    FROM clean_articles
    WHERE content IS NOT NULL AND LENGTH(content) > %s
)
SELECT id, title, source, content
FROM ranked
WHERE rn <= %s
ORDER BY source, rn
LIMIT %s
"""

GENERATION_PROMPT = """Buat {n} pasang tanya-jawab Bahasa Indonesia dari artikel berikut, \
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


def fetch_sample_articles() -> list[dict[str, Any]]:
    """Pull a source-diverse sample of clean_articles rows.

    Picks up to ARTICLES_PER_SOURCE longest articles per distinct source,
    then caps the overall sample at MAX_ARTICLES_TOTAL.

    Returns:
        List of dicts with id, title, source, content.
    """
    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SAMPLE_QUERY, (MIN_CONTENT_LENGTH, ARTICLES_PER_SOURCE, MAX_ARTICLES_TOTAL))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


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
    prompt = GENERATION_PROMPT.format(n=QA_PAIRS_PER_ARTICLE, title=article["title"], content=content)

    try:
        response = client.chat.completions.create(
            model=DATASET_GENERATOR_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
            extra_body=provider_body(DATASET_GENERATOR_PROVIDER),
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LLM generation failed for article {article['id']}: {e}")
        return []

    pairs = parse_qa_pairs(raw)
    if not pairs:
        logger.warning(f"No valid Q&A pairs parsed for article {article['id']} ({article['title']!r})")
    return pairs


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
    for i, article in enumerate(articles, start=1):
        logger.info(f"[{i}/{len(articles)}] Generating Q&A for: {article['title']!r} ({article['source']})")
        pairs = generate_qa_for_article(client, article)
        if not pairs:
            failed_articles += 1
        for pair in pairs:
            rows.append(
                {
                    "question": pair["question"],
                    "ground_truth": pair["answer"],
                    "article_id": article["id"],
                    "source_title": article["title"],
                    "source": article["source"],
                    "dataset_model": DATASET_GENERATOR_MODEL,
                    "dataset_provider": DATASET_GENERATOR_PROVIDER,
                }
            )
    logger.info(f"Articles with zero parsed pairs: {failed_articles}/{len(articles)}")
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
        "dataset_model",
        "dataset_provider",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    articles = fetch_sample_articles()
    logger.info(f"Sampled {len(articles)} articles across distinct sources")
    if not articles:
        logger.warning("No articles found matching sampling criteria; nothing to generate")
        return

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    rows = build_dataset(client, articles)

    write_csv(rows, OUTPUT_PATH)
    logger.info(f"Wrote {len(rows)} Q&A pairs from {len(articles)} articles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
