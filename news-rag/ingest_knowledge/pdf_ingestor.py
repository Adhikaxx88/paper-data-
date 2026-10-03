"""
PDF Knowledge Ingestor
======================
Bypass normal scraper→cleaner pipeline.
Langsung insert ke raw_articles + clean_articles sekaligus,
lalu embed & upsert ke Qdrant.

Usage:
    python pipeline/pdf_ingestor.py
    python pipeline/pdf_ingestor.py --dry-run      # preview tanpa insert
    python pipeline/pdf_ingestor.py --file "WHO_Guideline_Mental_Health_at_work.pdf"
"""

import os
import sys
import json
import uuid
import re
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import pymupdf as fitz
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from PIL import Image
import io
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector
from fastembed import TextEmbedding, SparseTextEmbedding

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
_env_local = Path(__file__).resolve().parent / ".env.local"
load_dotenv(dotenv_path=_env_local, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Paths
BASE_DIR   = Path(__file__).resolve().parent.parent   # root project
DOCS_DIR   = BASE_DIR / "data" / "knowledge"                     # folder PDF
CONFIG_DIR = BASE_DIR / "config"
METADATA_FILE = Path(__file__).resolve().parent / "pdf_metadata.json"

# Chunking
CHUNK_SIZE    = 512   # token/kata target per chunk
CHUNK_OVERLAP = 100   # overlap antar chunk

# DB
DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", "5433")),   # host-side port
    "user":     os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "dbname":   os.getenv("POSTGRES_DB"),
}

# Qdrant
QDRANT_URL       = os.getenv("QDRANT_URL", "http://localhost:6335")
COLLECTION_NAME  = os.getenv("COLLECTION_NAME", "data-paper-child")
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "intfloat/multilingual-e5-large")
SPARSE_MODEL_NAME = os.getenv("SPARSE_MODEL_NAME", "Qdrant/bm25")


# ──────────────────────────────────────────────
# 1. PDF Extraction
# ──────────────────────────────────────────────

def is_likely_header_footer(span: dict, page_height: float) -> bool:
    """Heuristik skip header/footer berdasarkan posisi y."""
    y0 = span.get("origin", (0, 0))[1]
    return y0 < page_height * 0.07 or y0 > page_height * 0.93


def extract_page_text(page: fitz.Page) -> str:
    """Ekstrak teks 1 halaman, skip header/footer."""
    page_height = page.rect.height
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    lines = []
    for block in blocks:
        if block.get("type") != 0:   # 0 = text block; skip images
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if is_likely_header_footer(span, page_height):
                    continue
                text = span.get("text", "").strip()
                if text:
                    lines.append(text)
    return " ".join(lines)


def is_empty_or_noise(text: str) -> bool:
    """True kalau halaman ini isinya kosong / cuma halaman cover / copyright."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) < 80:
        return True
    # Keyword yang biasanya muncul di halaman sampul / copyright
    noise_patterns = [
        r"^[\d\s\W]+$",           # cuma angka dan simbol
        r"all rights reserved",
        r"isbn[\s\-:]*[\d\-X]+",
        r"printed in",
        r"©\s*\d{4}",
    ]
    for pat in noise_patterns:
        if re.search(pat, cleaned.lower()):
            return True
    return False


def ocr_page(page) -> str:
    """Render halaman jadi gambar, lalu OCR. Fallback untuk PDF scan."""
    mat = fitz.Matrix(2, 2)  # 144 DPI
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="ind+eng")


def extract_pdf(pdf_path: Path) -> list[dict]:
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)          # ← simpan dulu sebelum close
    pages = []
    for page_num in range(total_pages):
        page = doc[page_num]
        text = extract_page_text(page)
        if is_empty_or_noise(text):
            text = ocr_page(page)   # fallback OCR untuk halaman scan
        if not is_empty_or_noise(text):
            pages.append({"page_num": page_num + 1, "text": text})
    doc.close()
    log.info(f"  → {len(pages)} non-empty pages dari {total_pages} total halaman")
    return pages


# ──────────────────────────────────────────────
# 2. Chunking (sliding window over words)
# ──────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Sliding window chunking atas kata-kata.
    chunk_size = max kata per chunk, overlap = kata yang diulang di chunk berikutnya.
    """
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks


def build_chunks_from_pages(pages: list[dict], filename: str) -> list[dict]:
    """
    Gabungkan teks semua halaman, lalu chunk.
    Returns list of {chunk_idx, text, page_start, url}.
    """
    # Gabungkan semua teks dulu (satu PDF = satu konteks)
    full_text = " ".join(p["text"] for p in pages)
    raw_chunks = chunk_text(full_text)

    chunks = []
    for i, chunk_text_val in enumerate(raw_chunks):
        # Synthetic URL: unik per chunk
        synthetic_url = f"pdf://docs/{filename}#chunk={i}"
        chunks.append({
            "chunk_idx": i,
            "text": chunk_text_val,
            "url": synthetic_url,
        })
    return chunks


# ──────────────────────────────────────────────
# 3. Embedding
# ──────────────────────────────────────────────

_dense_model: Optional[TextEmbedding] = None
_sparse_model: Optional[SparseTextEmbedding] = None


def get_models():
    global _dense_model, _sparse_model
    if _dense_model is None:
        log.info(f"Loading dense model: {DENSE_MODEL_NAME}")
        _dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    if _sparse_model is None:
        log.info(f"Loading sparse model: {SPARSE_MODEL_NAME}")
        _sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    return _dense_model, _sparse_model


def embed_texts(texts: list[str]) -> tuple[list[list[float]], list[SparseVector]]:
    """Embed batch teks → dense + sparse vectors."""
    dense_model, sparse_model = get_models()

    # Dense: multilingual-e5-large perlu prefix "passage: " untuk indexing
    prefixed = [f"passage: {t}" for t in texts]
    dense_vecs = list(dense_model.embed(prefixed))

    sparse_vecs = list(sparse_model.embed(texts))
    sparse_qdrant = [
        SparseVector(indices=sv.indices.tolist(), values=sv.values.tolist())
        for sv in sparse_vecs
    ]

    return [v.tolist() for v in dense_vecs], sparse_qdrant


# ──────────────────────────────────────────────
# 4. PostgreSQL Insert (bypass pipeline normal)
# ──────────────────────────────────────────────

def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


def insert_chunk_to_postgres(
    conn,
    chunk: dict,
    meta: dict,
    filename: str,
) -> str:
    """
    Insert 1 chunk ke raw_articles + clean_articles sekaligus.
    Returns raw_id (UUID string).
    """
    raw_id = str(uuid.uuid4())
    clean_id = str(uuid.uuid4())

    published_val = None
    if meta.get("published"):
        try:
            published_val = datetime.fromisoformat(meta["published"]).replace(tzinfo=timezone.utc)
        except ValueError:
            published_val = None

    # Kalau metadata punya URL canonical, gunakan itu sebagai "source URL" di title/metadata
    # tapi chunk URL-nya tetap synthetic (yang unique)
    title = f"[{meta.get('sub_area', 'doc').upper()}] {Path(filename).stem.replace('_', ' ').replace('-', ' ')}"

    with conn.cursor() as cur:
        # ── raw_articles ──
        cur.execute(
            """
            INSERT INTO raw_articles (
                id, url, title, content,
                source, topic_category, sub_area, keyword,
                published, language, source_type
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, 'id', 'pdf_knowledge'
            )
            ON CONFLICT (url) DO NOTHING
            RETURNING id
            """,
            (
                raw_id,
                chunk["url"],
                title,
                chunk["text"],
                meta.get("source"),
                meta.get("topic_category"),
                meta.get("sub_area"),
                meta.get("keyword"),
                published_val,
            ),
        )
        result = cur.fetchone()
        if result is None:
            # url sudah ada (ON CONFLICT) → cari raw_id yang existing
            cur.execute("SELECT id FROM raw_articles WHERE url = %s", (chunk["url"],))
            existing = cur.fetchone()
            return str(existing[0]) if existing else raw_id

        # ── clean_articles ──
        cur.execute(
            """
            INSERT INTO clean_articles (
                id, raw_id, url, title, content,
                source, topic_category, sub_area, keyword,
                published, source_type
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, 'pdf_knowledge'
            )
            ON CONFLICT (raw_id) DO NOTHING
            """,
            (
                clean_id,
                raw_id,
                chunk["url"],
                title,
                chunk["text"],
                meta.get("source"),
                meta.get("topic_category"),
                meta.get("sub_area"),
                meta.get("keyword"),
                published_val,
            ),
        )

    return raw_id


# ──────────────────────────────────────────────
# 5. Qdrant Upsert
# ──────────────────────────────────────────────

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def upsert_to_qdrant(
    qdrant: QdrantClient,
    chunks: list[dict],
    dense_vecs: list[list[float]],
    sparse_vecs: list[SparseVector],
    meta: dict,
    filename: str,
    raw_ids: list[str],
):
    """Upsert semua chunks dari 1 PDF ke Qdrant."""
    points = []
    for i, (chunk, dvec, svec, raw_id) in enumerate(
        zip(chunks, dense_vecs, sparse_vecs, raw_ids)
    ):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["url"]))
        points.append(
            PointStruct(
                id=point_id,
                vector={
                "dense": dvec,
                "bm25":  svec,
                },
                payload={
                    "raw_id":         raw_id,
                    "url":            chunk["url"],
                    "source":         meta.get("source"),
                    "topic_category": meta.get("topic_category"),
                    "sub_area":       meta.get("sub_area"),
                    "keyword":        meta.get("keyword"),
                    "published":      meta.get("published"),
                    "source_type":    "pdf_knowledge",
                    "filename":       filename,
                    "chunk_idx":      chunk["chunk_idx"],
                    "content":        chunk["text"],
                },
            )
        )

    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
    log.info(f"  → Upserted {len(points)} points ke Qdrant")


# ──────────────────────────────────────────────
# 6. Main Ingestion Loop
# ──────────────────────────────────────────────

def ingest_pdf(
    filename: str,
    meta: dict,
    conn,
    qdrant: QdrantClient,
    dry_run: bool = False,
) -> int:
    """Ingest 1 PDF. Returns jumlah chunks yang diproses."""
    pdf_path = DOCS_DIR / filename
    if not pdf_path.exists():
        log.warning(f"  ⚠️  File tidak ditemukan: {pdf_path}")
        return 0

    log.info(f"📄 Processing: {filename}")

    # Extract
    pages = extract_pdf(pdf_path)
    if not pages:
        log.warning(f"  ⚠️  Tidak ada halaman yang bisa diekstrak.")
        return 0

    # Chunk
    chunks = build_chunks_from_pages(pages, filename)
    log.info(f"  → {len(chunks)} chunks")

    if dry_run:
        log.info(f"  [DRY RUN] Skip insert. Contoh chunk[0]:\n    {chunks[0]['text'][:200]!r}")
        return len(chunks)

    # Embed semua chunks sekaligus (batch lebih efisien)
    texts = [c["text"] for c in chunks]
    log.info(f"  → Embedding {len(texts)} chunks...")
    dense_vecs, sparse_vecs = embed_texts(texts)

    # Insert ke Postgres
    raw_ids = []
    for chunk in chunks:
        raw_id = insert_chunk_to_postgres(conn, chunk, meta, filename)
        raw_ids.append(raw_id)
    conn.commit()
    log.info(f"  → Inserted {len(raw_ids)} rows ke PostgreSQL")

    # Upsert ke Qdrant
    upsert_to_qdrant(qdrant, chunks, dense_vecs, sparse_vecs, meta, filename, raw_ids)

    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF knowledge docs ke RAG pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Preview tanpa insert ke DB/Qdrant")
    parser.add_argument("--file", type=str, default=None, help="Ingest 1 file saja (by filename)")
    args = parser.parse_args()

    # Load metadata
    if not METADATA_FILE.exists():
        log.error(f"Metadata file tidak ditemukan: {METADATA_FILE}")
        sys.exit(1)

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        metadata: dict = json.load(f)

    log.info(f"Loaded metadata untuk {len(metadata)} PDF files")
    log.info(f"Docs dir: {DOCS_DIR}")
    log.info(f"DB: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    log.info(f"Qdrant: {QDRANT_URL} → collection: {COLLECTION_NAME}")

    if args.dry_run:
        log.info("⚠️  DRY RUN MODE — tidak ada data yang diinsert")

    # Filter ke 1 file kalau pakai --file
    if args.file:
        if args.file not in metadata:
            log.error(f"'{args.file}' tidak ada di metadata. Cek nama file-nya.")
            sys.exit(1)
        to_process = {args.file: metadata[args.file]}
    else:
        to_process = metadata

    # Koneksi
    conn   = None if args.dry_run else get_db_conn()
    qdrant = None if args.dry_run else get_qdrant_client()

    total_chunks = 0
    success = 0
    failed  = 0

    try:
        for filename, meta in to_process.items():
            try:
                n = ingest_pdf(filename, meta, conn, qdrant, dry_run=args.dry_run)
                total_chunks += n
                success += 1
            except Exception as e:
                log.error(f"  ❌ GAGAL proses {filename}: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                failed += 1
    finally:
        if conn:
            conn.close()

    log.info("")
    log.info("═══════════════════════════════════════")
    log.info(f"✅ Selesai: {success} file berhasil, {failed} gagal")
    log.info(f"   Total chunks: {total_chunks}")
    log.info("═══════════════════════════════════════")


if __name__ == "__main__":
    main()
