"""PostgreSQL access layer for articles, chunks, and chat history."""
import uuid
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras
from loguru import logger

from config import POSTGRES_URL


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Yield a PostgreSQL connection, committing on success and rolling back on error.

    Yields:
        An open psycopg2 connection.
    """
    conn = psycopg2.connect(POSTGRES_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    """Create all tables defined in db/schema.sql if they do not already exist."""
    import os

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
    logger.info("PostgreSQL schema initialized")


def get_article_id_by_url(url: str) -> Optional[uuid.UUID]:
    """Look up an existing article's id by its URL.

    Args:
        url: The article's source URL.

    Returns:
        The article UUID if it exists, otherwise None.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM articles WHERE url = %s", (url,))
            row = cur.fetchone()
            return row[0] if row else None


def upsert_article(
    source: str,
    title: str,
    article_date: Optional[date],
    url: str,
    category: str,
    article_id: Optional[uuid.UUID] = None,
) -> uuid.UUID:
    """Insert an article, or return the existing id if the URL is already stored.

    Args:
        source: Publisher name.
        title: Article title.
        article_date: Publication date.
        url: Canonical article URL, used as the dedup key.
        category: Topic/category label.
        article_id: Optional pre-generated UUID to use on insert.

    Returns:
        The UUID of the stored (new or existing) article.
    """
    existing = get_article_id_by_url(url)
    if existing:
        return existing

    new_id = article_id or uuid.uuid4()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles (id, source, title, date, url, category)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
                """,
                (new_id, source, title, article_date, url, category),
            )
            row = cur.fetchone()
            if row:
                return row[0]
    existing = get_article_id_by_url(url)
    return existing or new_id


def update_drive_url(article_id: uuid.UUID, drive_url: str) -> None:
    """Set the Google Drive URL for an article's PDF backup.

    Args:
        article_id: The article's UUID.
        drive_url: The uploaded PDF's shareable Drive URL.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE articles SET drive_url = %s WHERE id = %s",
                (drive_url, article_id),
            )


def has_drive_url(article_id: uuid.UUID) -> bool:
    """Check whether an article already has a Drive PDF backup recorded.

    Args:
        article_id: The article's UUID.

    Returns:
        True if the article exists and its drive_url is already set.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM articles WHERE id = %s AND drive_url IS NOT NULL", (article_id,))
            return cur.fetchone() is not None


def chunk_exists(chunk_id: uuid.UUID) -> bool:
    """Check whether a chunk has already been stored.

    Args:
        chunk_id: The chunk's UUID.

    Returns:
        True if the chunk is already in PostgreSQL.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM chunks WHERE chunk_id = %s", (chunk_id,))
            return cur.fetchone() is not None


def insert_chunk(chunk_id: uuid.UUID, article_id: uuid.UUID, chunk_index: int, chunk_text: str) -> None:
    """Store a chunk's text, skipping if it already exists.

    Args:
        chunk_id: The chunk's UUID.
        article_id: UUID of the parent article.
        chunk_index: Position of the chunk within the article.
        chunk_text: The chunk's text content.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (chunk_id, article_id, chunk_index, chunk_text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (chunk_id, article_id, chunk_index, chunk_text),
            )


def get_chunks_by_ids(chunk_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """Fetch chunk text joined with parent article metadata.

    Args:
        chunk_ids: Chunk UUIDs to fetch, typically from a Qdrant search result.

    Returns:
        List of dicts with chunk_text, title, source, date, category, url.
    """
    if not chunk_ids:
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.chunk_id, c.chunk_text, a.title, a.source, a.date, a.category, a.url
                FROM chunks c
                JOIN articles a ON a.id = c.article_id
                WHERE c.chunk_id = ANY(%s)
                """,
                (chunk_ids,),
            )
            return [dict(row) for row in cur.fetchall()]


def create_session(session_id: Optional[uuid.UUID] = None) -> uuid.UUID:
    """Create a new chat session.

    Args:
        session_id: Optional pre-generated UUID to use for the session.

    Returns:
        The UUID of the created (or already-existing) session.
    """
    new_id = session_id or uuid.uuid4()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (session_id) VALUES (%s) ON CONFLICT (session_id) DO NOTHING",
                (new_id,),
            )
    return new_id


def insert_message(session_id: uuid.UUID, role: str, content: str) -> None:
    """Persist a chat message.

    Args:
        session_id: The owning chat session's UUID.
        role: Either "user" or "assistant".
        content: Message text.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                (uuid.uuid4(), session_id, role, content),
            )


def get_all_messages(session_id: uuid.UUID) -> list[dict[str, Any]]:
    """Fetch every message in a session, oldest first.

    Args:
        session_id: The chat session's UUID.

    Returns:
        List of dicts with id, role, content, and created_at, ordered chronologically.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, role, content, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_recent_messages(session_id: uuid.UUID, limit: int) -> list[dict[str, Any]]:
    """Fetch the most recent messages in a session, oldest first.

    Args:
        session_id: The chat session's UUID.
        limit: Maximum number of messages to return.

    Returns:
        List of dicts with role and content, ordered chronologically.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT role, content, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
            return list(reversed(rows))
