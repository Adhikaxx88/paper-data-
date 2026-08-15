"""CLI entry point for running the full batch news RAG pipeline, or a single step."""
import argparse

from loguru import logger

from pipeline import chunker, cleaner, embedder, pdf_exporter, scraper

STEPS = ["scrape", "clean", "chunk", "embed", "pdf"]


def run_scrape() -> None:
    """Run the scrape step and log the resulting file."""
    path = scraper.run()
    logger.info(f"[scrape] wrote {path}")


def run_clean() -> None:
    """Run the clean step and log the resulting file."""
    path = cleaner.run()
    logger.info(f"[clean] wrote {path}")


def run_chunk() -> None:
    """Run the chunk step and log the resulting file."""
    path = chunker.run()
    logger.info(f"[chunk] wrote {path}")


def run_embed() -> dict[str, int]:
    """Run the embed step and log a summary.

    Returns:
        Summary dict from pipeline.embedder.run.
    """
    summary = embedder.run()
    logger.info(f"[embed] {summary}")
    return summary


def run_pdf() -> dict[str, int]:
    """Run the PDF export step and log a summary.

    Returns:
        Summary dict from pipeline.pdf_exporter.run.
    """
    summary = pdf_exporter.run()
    logger.info(f"[pdf] {summary}")
    return summary


STEP_FUNCS = {
    "scrape": run_scrape,
    "clean": run_clean,
    "chunk": run_chunk,
    "embed": run_embed,
    "pdf": run_pdf,
}


def run_all() -> None:
    """Run every pipeline step in order and print a final summary."""
    run_scrape()
    run_clean()
    run_chunk()
    embed_summary = run_embed()
    pdf_summary = run_pdf()

    print("\n=== Pipeline Summary ===")
    print(f"Chunks processed: {embed_summary['processed']}")
    print(f"Chunks newly indexed (vectors): {embed_summary['indexed']}")
    print(f"Articles exported to PDF/Drive: {pdf_summary['uploaded']}")


def main() -> None:
    """Parse CLI arguments and run the requested pipeline step(s)."""
    parser = argparse.ArgumentParser(description="Run the news RAG batch pipeline.")
    parser.add_argument("--step", choices=STEPS, help="Run a single pipeline step instead of all steps.")
    args = parser.parse_args()

    if args.step:
        STEP_FUNCS[args.step]()
    else:
        run_all()


if __name__ == "__main__":
    main()
