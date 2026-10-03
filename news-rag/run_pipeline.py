"""CLI entry point for running the full batch news RAG pipeline, or a single step."""
import argparse
from typing import Any, Optional

from loguru import logger

from db import postgres
from pipeline import chunker, cleaner, embedder, pdf_exporter, scraper

STEPS = ["scrape", "clean", "chunk", "embed", "pdf"]


def run_scrape() -> dict[str, int]:
    """Run the scrape step and log a summary.

    Returns:
        Summary dict from pipeline.scraper.fetch_and_store.
    """
    summary = scraper.fetch_and_store()
    logger.info(f"[scrape] {summary}")
    return summary


def run_clean() -> dict[str, int]:
    """Run the clean step and log a summary.

    Returns:
        Summary dict from pipeline.cleaner.clean_and_store.
    """
    summary = cleaner.clean_and_store()
    logger.info(f"[clean] {summary}")
    return summary


def run_chunk() -> list[dict[str, Any]]:
    """Run the chunk step (read clean_articles from PostgreSQL) and log a summary.

    Returns:
        List of chunk dicts, ready for pipeline.embedder.embed_and_store.
    """
    chunks = chunker.chunk_articles()
    articles_processed = len({c["article_id"] for c in chunks})
    logger.info(f"[chunk] {len(chunks)} chunks from {articles_processed} articles")
    return chunks


def run_embed(chunks: Optional[list[dict[str, Any]]] = None) -> dict[str, int]:
    """Run the embed step and log a summary.

    Args:
        chunks: Optional pre-computed chunks (from run_chunk()). If omitted,
            chunks are (re)computed from PostgreSQL clean_articles — used
            when running `--step embed` on its own.

    Returns:
        Summary dict from pipeline.embedder.embed_and_store.
    """
    if chunks is None:
        chunks = chunker.chunk_articles()
    summary = embedder.embed_and_store(chunks)
    logger.info(f"[embed] {summary}")
    return summary


def run_pdf(pdf_dir: Optional[str] = None, since_date: Optional[str] = None) -> dict[str, int]:
    """Run the PDF export step and log a summary.

    Args:
        pdf_dir: Optional output directory override, passed through to
            pipeline.pdf_exporter.export_and_upload.
        since_date: Optional ISO date string; only articles created on or
            after this date are exported.

    Returns:
        Summary dict from pipeline.pdf_exporter.export_and_upload.
    """
    summary = pdf_exporter.export_and_upload(output_dir=pdf_dir, since_date=since_date)
    logger.info(f"[pdf] {summary}")
    return summary


STEP_FUNCS = {
    "scrape": run_scrape,
    "clean": run_clean,
    "chunk": run_chunk,
    "embed": run_embed,
    "pdf": run_pdf,
}


def run_all(pdf_dir: Optional[str] = None, since_date: Optional[str] = None) -> None:
    """Run every pipeline step in order and print a final summary.

    Args:
        pdf_dir: Optional output directory override for the PDF export step.
        since_date: Optional ISO date string limiting the PDF export step to
            articles created on or after this date.
    """
    run_scrape()
    run_clean()
    chunks = run_chunk()
    embed_summary = run_embed(chunks)
    pdf_summary = run_pdf(pdf_dir=pdf_dir, since_date=since_date)

    print("\n=== Pipeline Summary ===")
    print(f"Chunks processed: {embed_summary['processed']}")
    print(f"Chunks newly indexed (vectors): {embed_summary['indexed']}")
    print(f"Articles exported to PDF/Drive: {pdf_summary['exported']}")


def main() -> None:
    """Parse CLI arguments and run the requested pipeline step(s)."""
    parser = argparse.ArgumentParser(description="Run the news RAG batch pipeline.")
    parser.add_argument("--step", choices=STEPS, help="Run a single pipeline step instead of all steps.")
    parser.add_argument(
        "--pdf-dir", default=None, help="Output directory for the pdf step (overrides DATA_PDF_DIR)."
    )
    parser.add_argument(
        "--since-date",
        default=None,
        help="ISO date (e.g. 2026-08-30); the pdf step only exports articles created on or after this date.",
    )
    args = parser.parse_args()

    postgres.init_schema()
    postgres.migrate_add_sub_area()
    postgres.migrate_add_keyword_fields()
    postgres.migrate_add_language_field()

    if args.step:
        if args.step == "pdf":
            run_pdf(pdf_dir=args.pdf_dir, since_date=args.since_date)
        else:
            STEP_FUNCS[args.step]()
    else:
        run_all(pdf_dir=args.pdf_dir, since_date=args.since_date)


if __name__ == "__main__":
    main()
