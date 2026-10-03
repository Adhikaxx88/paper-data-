"""Output protection: sanitize search results before they leave the API."""
import re
from typing import Any

_MAX_CHUNK_CHARS = 500

_REDACT_PATTERNS = [
    re.compile(re.escape(phrase), re.IGNORECASE)
    for phrase in ("system prompt", "my instructions are", "I was told to", "ignore previous")
]

_ALLOWED_FIELDS = ["title", "url", "keyword", "language", "chunk_text", "chunk_index", "article_id"]


def protect_output(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Truncate, redact, and field-allowlist a list of search results.

    Args:
        results: Raw result dicts from backend.retrieval.searcher.hybrid_search.

    Returns:
        New list of cleaned result dicts, each containing only allowlisted fields.
    """
    cleaned = []
    for result in results:
        chunk_text = result.get("chunk_text") or ""

        for pattern in _REDACT_PATTERNS:
            chunk_text = pattern.sub("[REDACTED]", chunk_text)

        truncated = len(chunk_text) > _MAX_CHUNK_CHARS
        chunk_text = chunk_text[:_MAX_CHUNK_CHARS]
        if truncated:
            chunk_text += "..."

        item = {field: result.get(field) for field in _ALLOWED_FIELDS}
        item["chunk_text"] = chunk_text
        cleaned.append(item)

    return cleaned
