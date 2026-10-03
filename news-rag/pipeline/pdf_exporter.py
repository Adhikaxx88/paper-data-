"""Export clean_articles to PDF, organized by language/topic_category/sub_area."""
import os
import re
from pathlib import Path
from typing import Any, Optional

from fpdf import FPDF
from loguru import logger

from config import DATA_PDF_DIR
from db.postgres import get_articles_without_drive_url, get_connection


def slugify(text: str) -> str:
    """Convert text into a filesystem-safe slug.

    Args:
        text: Arbitrary text, typically an article title or category.

    Returns:
        Lowercase slug with only alphanumerics and hyphens.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:80] or "untitled"


def _create_pdf(article: dict[str, Any], subfolder: Optional[str] = None, output_dir: str = DATA_PDF_DIR) -> Path:
    """Render a clean_articles row as a PDF file under output_dir, organized as
    topic_category/sub_area/filename.pdf.

    Uses a Unicode TTF font when the DejaVu fonts are available on the
    system (common on Linux), falling back to the latin-1-only core
    Helvetica font (with unsupported characters replaced) otherwise.

    Args:
        article: Clean article dict with id, title, source, published, url, content, topic_category.
        subfolder: Optional sub_area name to nest the PDF under (in addition to topic_category).
        output_dir: Root directory to write the PDF under. Defaults to DATA_PDF_DIR.

    Returns:
        Path to the generated PDF file.
    """
    category_dir = Path(output_dir) / slugify(article.get("language") or "en")
    category_dir = category_dir / slugify(article.get("topic_category") or "uncategorized")
    if subfolder:
        category_dir = category_dir / slugify(subfolder)
    category_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = category_dir / f"{slugify(article['title'])}-{str(article['id'])[:8]}.pdf"

    pdf = FPDF()
    pdf.add_page()

    unicode_font = _register_unicode_font(pdf)
    title_style = (unicode_font, "B", 16) if unicode_font else ("Helvetica", "B", 16)
    meta_style = (unicode_font, "", 10) if unicode_font else ("Helvetica", "", 10)
    body_style = (unicode_font, "", 11) if unicode_font else ("Helvetica", "", 11)

    def text(value: Any) -> str:
        s = str(value or "")
        return s if unicode_font else s.encode("latin-1", "replace").decode("latin-1")

    pdf.set_font(*title_style)
    pdf.multi_cell(0, 10, text(article.get("title")))
    pdf.ln(2)

    pdf.set_font(*meta_style)
    pdf.multi_cell(
        0,
        6,
        text(
            f"Source: {article.get('source')} | Published: {article.get('published')} | "
            f"URL: {article.get('url')}"
        ),
    )
    pdf.ln(4)

    pdf.set_font(*body_style)
    pdf.multi_cell(0, 6, text(article.get("content")))

    pdf.output(str(pdf_path))
    return pdf_path


def _register_unicode_font(pdf: FPDF) -> Optional[str]:
    """Register the DejaVu Sans TTF font with fpdf2 if it's installed on the system.

    Returns:
        "DejaVu" if the font was registered, otherwise None (caller should
        fall back to the latin-1-only core Helvetica font).
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            pdf.add_font("DejaVu", "", path)
            pdf.add_font("DejaVu", "B", path)
            return "DejaVu"
    return None


def export_and_upload(output_dir: Optional[str] = None, since_date: Optional[str] = None) -> dict[str, int]:
    """Export clean_articles rows without a drive_url to PDF, organized under
    output_dir by language/topic_category/sub_area.

    Args:
        output_dir: Optional root directory to write PDFs under. Defaults to DATA_PDF_DIR.
        since_date: Optional ISO date string (e.g. '2026-08-30'). If provided, only
            articles created on or after this date are exported.

    Returns:
        Summary dict: exported, failed.
    """
    target_dir = output_dir or DATA_PDF_DIR
    os.makedirs(target_dir, exist_ok=True)

    conn = get_connection()
    try:
        articles = get_articles_without_drive_url(conn, since_date=since_date)

        exported, failed = 0, 0
        for article in articles:
            try:
                _create_pdf(article, subfolder=article.get("sub_area"), output_dir=target_dir)
                exported += 1
            except Exception as e:
                logger.error(f"Failed export {article.get('url')}: {e}")
                failed += 1
    finally:
        conn.close()

    summary = {"exported": exported, "failed": failed}
    logger.info(f"PDF export complete: {summary}")
    return summary


if __name__ == "__main__":
    export_and_upload()
