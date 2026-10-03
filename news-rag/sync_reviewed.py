"""Sync a professor-reviewed classified/ folder of PDFs back into PostgreSQL.

Expects data/classified/<en|id>/<topic_category>/[sub_area]/*.pdf, populated by
downloading pipeline-exported PDFs from Google Drive after professor review.
Filenames follow pipeline.pdf_exporter's `{slugified-title}-{8char-id}.pdf`
convention. The professor marks a review decision by including "ok" anywhere
in the filename:

  "ok" appears in the filename (case-insensitive) -> approved: keep
  "ok" does not appear                            -> rejected: delete from the database

New PDFs the professor adds (not yet in the database) are not handled here;
only existing database articles are approved/rejected.
"""
import argparse
from pathlib import Path
from typing import Optional

from loguru import logger

from db.postgres import get_connection

CLASSIFIED_DIR = Path(__file__).resolve().parent / "data" / "classified-2"


def _classify_filename(stem: str) -> str:
    """Classify a PDF filename (without extension) by whether "ok" appears in it.

    Args:
        stem: Filename without extension.

    Returns:
        "approve" if "ok" appears anywhere in stem (case-insensitive), else "reject".
    """
    if "ok" in stem.lower():
        return "approve"
    return "reject"


def _extract_article_id_prefix(stem: str) -> Optional[str]:
    """Recover the 8-char article id from a PDF's filename.

    Args:
        stem: Filename without extension.

    Returns:
        The trailing hyphen-separated segment (the article id), or None if
        the filename has no hyphen-separated segments.
    """
    segments = [s for s in stem.split("-") if s]
    return segments[-1] if segments else None


def _delete_rejected(conn, article_id_prefix: str) -> None:
    """Delete clean_articles and raw_articles rows whose id starts with article_id_prefix.

    Args:
        conn: An open connection from db.postgres.get_connection().
        article_id_prefix: The 8-char id prefix recovered from the filename.
    """
    pattern = f"{article_id_prefix}%"
    with conn.cursor() as cur:
        cur.execute("DELETE FROM clean_articles WHERE id::text LIKE %s", (pattern,))
        clean_deleted = cur.rowcount
        cur.execute("DELETE FROM raw_articles WHERE id::text LIKE %s", (pattern,))
        raw_deleted = cur.rowcount
    conn.commit()
    logger.info(
        f"Deleted {clean_deleted} clean_articles row(s) and {raw_deleted} raw_articles "
        f"row(s) with id LIKE '{pattern}'"
    )


def sync(dry_run: bool = False) -> dict[str, int]:
    """Walk CLASSIFIED_DIR and apply professor review decisions to existing DB articles.

    Only handles approve/reject of articles already in the database; PDFs the
    professor newly added (not yet in the database) are not imported here.

    Args:
        dry_run: If True, log what would happen without touching the database.

    Returns:
        Summary dict: deleted, kept, failed.
    """
    deleted = kept = failed = 0

    conn = get_connection()
    try:
        for pdf_path in sorted(CLASSIFIED_DIR.rglob("*.pdf")):
            stem = pdf_path.stem
            classification = _classify_filename(stem)

            if classification == "approve":
                logger.debug(f"Approved, keeping: {pdf_path.name}")
                kept += 1
                continue

            # classification == "reject"
            article_id_prefix = _extract_article_id_prefix(stem)
            if not article_id_prefix:
                logger.error(f"Could not recover article id from {pdf_path.name}")
                failed += 1
                continue
            if dry_run:
                logger.info(
                    f"[dry-run] Would delete clean_articles/raw_articles rows "
                    f"with id LIKE '{article_id_prefix}%' (from {pdf_path.name})"
                )
            else:
                try:
                    _delete_rejected(conn, article_id_prefix)
                except Exception as e:
                    logger.error(f"Failed to delete for {pdf_path.name}: {e}")
                    failed += 1
                    continue
            deleted += 1
    finally:
        conn.close()

    summary = {"deleted": deleted, "kept": kept, "failed": failed}
    logger.info(f"Sync complete: {summary}")
    return summary


def main() -> None:
    """Parse CLI arguments and run the reviewed-folder sync."""
    parser = argparse.ArgumentParser(description="Sync a professor-reviewed classified/ folder into the database.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without touching the database.")
    args = parser.parse_args()

    summary = sync(dry_run=args.dry_run)
    print("\n=== Sync Summary ===")
    for key in ("deleted", "kept", "failed"):
        print(f"{key}: {summary[key]}")


if __name__ == "__main__":
    main()
