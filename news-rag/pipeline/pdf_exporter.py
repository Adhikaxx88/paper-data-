"""Export cleaned articles to PDF, organize by category, and back them up to Google Drive."""
import json
import os
import re
import uuid
from typing import Any, Optional

from fpdf import FPDF
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from loguru import logger

from config import DATA_CLEAN_DIR, DATA_PDF_DIR, GOOGLE_DRIVE_CREDENTIALS_PATH
from db import postgres
from pipeline.chunker import derive_article_id

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_drive_service: Optional[Resource] = None
_folder_cache: dict[str, str] = {}


def slugify(text: str) -> str:
    """Convert a title into a filesystem-safe slug.

    Args:
        text: Arbitrary text, typically an article title.

    Returns:
        Lowercase slug with only alphanumerics and hyphens.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:80] or "untitled"


def article_to_pdf(article: dict[str, Any], out_path: str) -> None:
    """Render a single article as a PDF file.

    Args:
        article: Cleaned article dict with title, source, date, url, content.
        out_path: Destination path for the generated PDF.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 10, article["title"])
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, f"Source: {article['source']} | Date: {article['date']} | URL: {article['url']}")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, article["content"])
    pdf.output(out_path)


def get_drive_service() -> Resource:
    """Return a lazily-initialized, module-level Google Drive API client.

    Returns:
        An authenticated Drive v3 service resource.
    """
    global _drive_service
    if _drive_service is None:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_DRIVE_CREDENTIALS_PATH, scopes=_DRIVE_SCOPES
        )
        _drive_service = build("drive", "v3", credentials=credentials)
    return _drive_service


def get_or_create_folder(category: str) -> str:
    """Find or create a Google Drive folder for a category, caching the result.

    Args:
        category: Article category, used as the folder name.

    Returns:
        The Drive folder id.
    """
    if category in _folder_cache:
        return _folder_cache[category]

    service = get_drive_service()
    query = (
        f"name = '{category}' and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        metadata = {"name": category, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=metadata, fields="id").execute()
        folder_id = folder["id"]

    _folder_cache[category] = folder_id
    return folder_id


def upload_to_drive(local_path: str, category: str) -> str:
    """Upload a PDF to the category's Drive folder and return its shareable link.

    Args:
        local_path: Path to the local PDF file.
        category: Article category, used to pick the destination folder.

    Returns:
        The uploaded file's webViewLink.
    """
    service = get_drive_service()
    folder_id = get_or_create_folder(category)
    metadata = {"name": os.path.basename(local_path), "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype="application/pdf")
    uploaded = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return uploaded["webViewLink"]


def export_article(article: dict[str, Any]) -> Optional[str]:
    """Render, save, and upload the PDF for a single article, then update PostgreSQL.

    Skips articles whose PDF has already been uploaded (drive_url already set).

    Args:
        article: Cleaned article dict.

    Returns:
        The Drive URL if newly uploaded, otherwise None.
    """
    article_id = derive_article_id(article["url"])
    if postgres.has_drive_url(article_id):
        return None

    category_dir = os.path.join(DATA_PDF_DIR, slugify(article["category"]))
    os.makedirs(category_dir, exist_ok=True)
    pdf_path = os.path.join(category_dir, f"{slugify(article['title'])}.pdf")

    if not os.path.exists(pdf_path):
        article_to_pdf(article, pdf_path)

    try:
        drive_url = upload_to_drive(pdf_path, article["category"])
    except Exception as e:
        logger.error(f"Failed to upload PDF for '{article['title'][:50]}' to Drive: {e}")
        return None

    postgres.update_drive_url(article_id, drive_url)
    return drive_url


def run(clean_file: Optional[str] = None) -> dict[str, int]:
    """Export all (or one) cleaned article file(s) to PDF and upload to Drive.

    Args:
        clean_file: Optional specific cleaned JSON file to process. Defaults to
            processing every file in data/clean/.

    Returns:
        Summary dict with counts of processed and uploaded articles.
    """
    os.makedirs(DATA_PDF_DIR, exist_ok=True)
    files = (
        [clean_file]
        if clean_file
        else [os.path.join(DATA_CLEAN_DIR, f) for f in os.listdir(DATA_CLEAN_DIR) if f.endswith(".json")]
    )

    processed = 0
    uploaded = 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                articles = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read cleaned file {path}: {e}")
            continue

        for article in articles:
            processed += 1
            if export_article(article):
                uploaded += 1

    logger.info(f"PDF export complete: {processed} processed, {uploaded} uploaded to Drive")
    return {"processed": processed, "uploaded": uploaded}


if __name__ == "__main__":
    run()
