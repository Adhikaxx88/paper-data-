"""PostgreSQL access layer for articles, chunks, and chat history."""
import uuid
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras
from loguru import logger

from config import POSTGRES_URL

# Without this, psycopg2 can't adapt Python uuid.UUID objects passed as
# query params (raises "can't adapt type 'UUID'") — every function here
# that inserts/filters by a UUID column relies on it.
psycopg2.extras.register_uuid()


@contextmanager
def _connection_scope() -> Iterator[psycopg2.extensions.connection]:
    """Yield a PostgreSQL connection, committing on success and rolling back on error.

    Used internally by functions that manage their own short-lived connection.
    Callers that need a connection to pass around across several calls (e.g.
    the scrape/clean/pdf pipeline steps) should use `get_connection()` instead.

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


def get_connection() -> psycopg2.extensions.connection:
    """Open a new PostgreSQL connection for the caller to manage directly.

    Unlike `_connection_scope()`, the caller is responsible for committing
    and closing this connection. Intended for pipeline steps that perform
    many operations over one connection (see pipeline/scraper.py,
    pipeline/cleaner.py, pipeline/pdf_exporter.py).

    Returns:
        An open psycopg2 connection.
    """
    return psycopg2.connect(POSTGRES_URL)


def init_schema() -> None:
    """Create all tables defined in db/schema.sql if they do not already exist."""
    import os

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with _connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
    logger.info("PostgreSQL schema initialized")


def migrate_add_sub_area() -> None:
    """Add the sub_area column to raw_articles/clean_articles if missing.

    Safe to run against a database created before sub_area was introduced.
    """
    with _connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE raw_articles ADD COLUMN IF NOT EXISTS sub_area TEXT;
                ALTER TABLE clean_articles ADD COLUMN IF NOT EXISTS sub_area TEXT;
                """
            )
    logger.info("PostgreSQL migration: sub_area column ensured")


def migrate_add_keyword_fields() -> None:
    """Add the keyword columns to raw_articles/clean_articles/chunks if missing.

    Safe to run against a database created before keyword was introduced.
    """
    with _connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE raw_articles ADD COLUMN IF NOT EXISTS keyword TEXT;
                ALTER TABLE clean_articles ADD COLUMN IF NOT EXISTS keyword TEXT;
                ALTER TABLE chunks ADD COLUMN IF NOT EXISTS keyword TEXT;
                """
            )
    logger.info("PostgreSQL migration: keyword column ensured")


def migrate_add_language_field() -> None:
    """Add the language column to raw_articles/clean_articles if missing.

    Safe to run against a database created before language was introduced.
    """
    with _connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE raw_articles ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en';
                ALTER TABLE clean_articles ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en';
                """
            )
    logger.info("PostgreSQL migration: language column ensured")


def get_article_id_by_url(url: str) -> Optional[uuid.UUID]:
    """Look up an existing article's id by its URL.

    Args:
        url: The article's source URL.

    Returns:
        The article UUID if it exists, otherwise None.
    """
    with _connection_scope() as conn:
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
    with _connection_scope() as conn:
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


def insert_raw_article(conn: psycopg2.extensions.connection, article: dict[str, Any]) -> Optional[uuid.UUID]:
    """Insert a scraped article into raw_articles, deduplicated by URL.

    Args:
        conn: An open connection from `get_connection()`.
        article: Dict with url, title, content, published, source,
            topic_category, sub_area, search_query, keyword, language.

    Returns:
        The new row's UUID if inserted, or None if the URL was already present.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_articles (
                url, title, content, published, source, topic_category, sub_area,
                search_query, keyword, language
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            RETURNING id
            """,
            (
                article["url"],
                article.get("title"),
                article.get("content"),
                article.get("published"),
                article.get("source"),
                article.get("topic_category"),
                article.get("sub_area"),
                article.get("search_query"),
                article.get("keyword"),
                article.get("language", "en"),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return row[0] if row else None


def get_uncleaned_raw_articles(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    """Fetch raw_articles rows that have no corresponding clean_articles row yet.

    Args:
        conn: An open connection from `get_connection()`.

    Returns:
        List of raw article dicts, oldest first.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT ra.*
            FROM raw_articles ra
            LEFT JOIN clean_articles ca ON ca.raw_id = ra.id
            WHERE ca.id IS NULL
            ORDER BY ra.created_at ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def url_exists_in_clean(conn: psycopg2.extensions.connection, url: str) -> bool:
    """Check whether a URL already exists in clean_articles.

    Used by the cleaner to skip duplicate articles before attempting an insert.

    Args:
        conn: An open connection from `get_connection()`.
        url: The article URL to look up.

    Returns:
        True if the URL is already present in clean_articles, False otherwise.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM clean_articles WHERE url = %s LIMIT 1", (url,))
        return cur.fetchone() is not None


def insert_clean_article(conn: psycopg2.extensions.connection, article: dict[str, Any]) -> Optional[uuid.UUID]:
    """Insert a cleaned article into clean_articles.

    Args:
        conn: An open connection from `get_connection()`.
        article: Dict with raw_id, url, title, content, published, source,
            topic_category, sub_area, keyword, language.

    Returns:
        The new row's UUID if inserted, or None if a clean row for this
        raw_id already exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clean_articles (
                raw_id, url, title, content, published, source, topic_category, sub_area,
                keyword, language
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (raw_id) DO NOTHING
            RETURNING id
            """,
            (
                article["raw_id"],
                article.get("url"),
                article.get("title"),
                article.get("content"),
                article.get("published"),
                article.get("source"),
                article.get("topic_category"),
                article.get("sub_area"),
                article.get("keyword"),
                article.get("language", "en"),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return row[0] if row else None


def get_all_clean_articles(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    """Fetch every clean_articles row, for the chunker to split into chunks.

    Args:
        conn: An open connection from `get_connection()`.

    Returns:
        List of dicts with id, url, title, content, published, source, topic_category,
        sub_area, keyword, language.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, url, title, content, published, source, topic_category, sub_area, "
            "keyword, language "
            "FROM clean_articles ORDER BY created_at ASC"
        )
        return [dict(row) for row in cur.fetchall()]


def get_articles_without_drive_url(
    conn: psycopg2.extensions.connection, since_date: Optional[str] = None
) -> list[dict[str, Any]]:
    """Fetch clean_articles rows that have not yet been uploaded to Drive.

    Args:
        conn: An open connection from `get_connection()`.
        since_date: Optional ISO date string (e.g. '2026-08-30'). If provided,
            only rows created on or after this date are returned.

    Returns:
        List of clean article dicts, oldest first.
    """
    query = "SELECT * FROM clean_articles WHERE drive_url IS NULL"
    params: tuple = ()
    if since_date:
        query += " AND created_at >= %s"
        params = (since_date,)
    query += " ORDER BY created_at ASC"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def update_drive_url(conn: psycopg2.extensions.connection, article_id: uuid.UUID, drive_url: str) -> None:
    """Set the Google Drive URL for a clean article's PDF backup.

    Args:
        conn: An open connection from `get_connection()`.
        article_id: The clean_articles row's UUID.
        drive_url: The uploaded PDF's shareable Drive URL.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE clean_articles SET drive_url = %s WHERE id = %s",
            (drive_url, article_id),
        )
    conn.commit()


def chunk_exists(chunk_id: uuid.UUID) -> bool:
    """Check whether a chunk has already been stored.

    Args:
        chunk_id: The chunk's UUID.

    Returns:
        True if the chunk is already in PostgreSQL.
    """
    with _connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM chunks WHERE chunk_id = %s", (chunk_id,))
            return cur.fetchone() is not None


def insert_chunk(
    chunk_id: uuid.UUID,
    article_id: uuid.UUID,
    chunk_index: int,
    chunk_text: str,
    keyword: Optional[str] = None,
) -> None:
    """Store a chunk's text, skipping if it already exists.

    Args:
        chunk_id: The chunk's UUID.
        article_id: UUID of the parent article.
        chunk_index: Position of the chunk within the article.
        chunk_text: The chunk's text content.
        keyword: The search query that surfaced the parent article.
    """
    with _connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (chunk_id, article_id, chunk_index, chunk_text, keyword)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (chunk_id, article_id, chunk_index, chunk_text, keyword),
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
    with _connection_scope() as conn:
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
    with _connection_scope() as conn:
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
    with _connection_scope() as conn:
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
    with _connection_scope() as conn:
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
    with _connection_scope() as conn:
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