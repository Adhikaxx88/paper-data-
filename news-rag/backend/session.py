"""In-memory session store for search query history.

Sessions live only for the lifetime of the backend process — this is a
lightweight conversational-context store for guardrails.multiturn_check,
not a durable chat history (see db/postgres.py for the persisted chat
session tables used by the /api/chat endpoint).
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

_SESSION_TTL = timedelta(hours=1)
_MAX_HISTORY = 20


@dataclass
class SessionData:
    """In-memory record of one session's query history.

    Attributes:
        session_id: The session's id.
        history: Prior query texts, oldest first, capped at _MAX_HISTORY.
        created_at: When the session was first created.
        last_active: When the session was last read or appended to.
    """

    session_id: str
    history: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


sessions: dict[str, SessionData] = {}


def _is_expired(session: SessionData) -> bool:
    return datetime.now(timezone.utc) - session.last_active > _SESSION_TTL


def get_or_create_session(session_id: str) -> SessionData:
    """Return the session for session_id, creating a fresh one if needed.

    A fresh session is created (with a new uuid4 id) when session_id is
    empty, unknown, or expired.

    Args:
        session_id: Client-supplied session id, or "" for a new session.

    Returns:
        The (possibly newly created) SessionData.
    """
    existing = sessions.get(session_id) if session_id else None
    if existing is not None and _is_expired(existing):
        del sessions[session_id]
        existing = None

    if existing is not None:
        existing.last_active = datetime.now(timezone.utc)
        return existing

    new_id = session_id or str(uuid.uuid4())
    session = SessionData(session_id=new_id)
    sessions[new_id] = session
    return session


def append_to_session(session_id: str, query: str) -> None:
    """Append a query to a session's history, keeping only the last 20.

    Args:
        session_id: The session to append to. No-op if it doesn't exist.
        query: The query text to record.
    """
    session = sessions.get(session_id)
    if session is None:
        return
    session.history.append(query)
    session.history = session.history[-_MAX_HISTORY:]
    session.last_active = datetime.now(timezone.utc)


def get_history(session_id: str) -> list[str]:
    """Return a session's query history, oldest first.

    Args:
        session_id: The session to look up.

    Returns:
        The session's history, or an empty list if the session doesn't
        exist or has expired.
    """
    session = sessions.get(session_id)
    if session is None or _is_expired(session):
        return []
    return session.history
