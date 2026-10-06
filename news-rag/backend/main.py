"""FastAPI backend exposing the news RAG pipeline as an HTTP API for the React frontend."""
import re
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Make the project root importable regardless of whether this module is run
# as "backend.main" (docker-compose: cwd=project root) or as bare "main"
# (backend/start.bat: cwd=backend/) — both need `config`, `db`, `rag`,
# `vectorization`, and `backend.*` to resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from backend.retrieval.searcher import get_dense_model
from backend.routers.search import router as search_router
from db import postgres
from rag.pipeline import ask


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the dense embedding model at startup (already loaded on import, cached here)."""
    app.state.model = get_dense_model()
    logger.info("Dense embedding model ready")
    yield


app = FastAPI(title="News RAG Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5888", "http://127.0.0.1:5888"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api")


class SessionResponse(BaseModel):
    session_id: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class HistoryResponse(BaseModel):
    messages: list[MessageOut]


class ChatRequest(BaseModel):
    session_id: str
    message: str
    # Evaluation-only: return the raw retrieved sources even when the UI
    # would hide them, so RAGAS/DeepEval get the real contexts.
    bypass_source_filter: bool = False


class SourceOut(BaseModel):
    title: str
    source: str
    date: str
    score: float
    url: str
    article_id: str
    content: str


_HASH_SUFFIX_RE = re.compile(r"\s+[0-9a-f]{8}(-[0-9a-f]+)?$", re.IGNORECASE)


def _clean_title(title: str) -> str:
    """Strip ingestion artifacts from an article title.

    Manually uploaded (drive_reviewed) filenames pick up a trailing content
    hash (e.g. "... medcom id c2e43613") and use underscores in place of
    spaces (e.g. "KESEHATAN MENTAL_ Orang Tua Abai..."). Applied to every
    title, not just drive_reviewed ones, since it's a no-op when neither
    artifact is present.

    Args:
        title: The raw article title from the chunk payload.

    Returns:
        The title with any trailing hash suffix removed, underscores turned
        into spaces, and whitespace collapsed/trimmed.
    """
    if not title:
        return ""
    cleaned = _HASH_SUFFIX_RE.sub("", title)
    cleaned = cleaned.replace("_", " ")
    return " ".join(cleaned.split())


def _truncate_at_word(text: str, max_len: int = 40) -> str:
    """Truncate text to at most max_len chars, breaking on a word boundary.

    Args:
        text: The text to truncate.
        max_len: Maximum length before adding an ellipsis.

    Returns:
        text unchanged if it already fits; otherwise cut at the last space
        before max_len (or hard-cut if there's no space to break on), with
        "..." appended.
    """
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def _display_source(clean_title: str, source: str) -> str:
    """Resolve a human-readable source label.

    Manually uploaded articles are stored with source="drive_reviewed" (the
    ingestion path, not a publication name), which is meaningless to a
    reader — fall back to the (already-cleaned) article title in that case.

    Args:
        clean_title: The article's title, already run through _clean_title.
        source: The raw source value from the chunk payload.

    Returns:
        "drive_reviewed" articles: clean_title truncated to 40 chars at a
        word boundary. Otherwise: the source unchanged.
    """
    if source != "drive_reviewed":
        return source
    return _truncate_at_word(clean_title, 40)


MIN_SOURCE_SCORE = 0.3
NO_CONTEXT_PHRASE = "tidak ditemukan informasi yang relevan"


def _should_hide_sources(answer: str, raw_sources: list[dict]) -> bool:
    """Decide whether the citations backing an answer are worth showing.

    Surfacing sources next to an answer the model itself flagged as
    unsupported, or that were only weakly related to the question, misleads
    the reader into thinking the answer is better-grounded than it is. Note:
    this endpoint (rag.pipeline.ask) doesn't run any prompt-injection
    guardrail — that check exists only on backend/routers/search.py's
    /api/search path — so there's nothing to gate on for that case here.

    Args:
        answer: The generated answer text.
        raw_sources: Retrieved chunk dicts from rag.retriever.retrieve,
            each with a "score" key (RRF fusion score).

    Returns:
        True if sources should be omitted from the response.
    """
    if not raw_sources:
        return True
    if NO_CONTEXT_PHRASE in answer.lower():
        return True
    if max(s["score"] for s in raw_sources) < MIN_SOURCE_SCORE:
        return True
    return False


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    # True when the LLM call failed and `answer` is the apology text, not a real answer.
    generation_failed: bool = False


@app.post("/api/session", response_model=SessionResponse)
def create_session() -> SessionResponse:
    """Create a new chat session in PostgreSQL.

    Returns:
        The newly created session's id.
    """
    session_id = postgres.create_session()
    return SessionResponse(session_id=str(session_id))


@app.get("/api/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str) -> HistoryResponse:
    """Fetch every message previously recorded for a chat session.

    Args:
        session_id: UUID of the chat session.

    Returns:
        All messages for the session, oldest first.

    Raises:
        HTTPException: 400 if session_id is not a valid UUID.
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    rows = postgres.get_all_messages(session_uuid)
    messages = [
        MessageOut(
            id=str(row["id"]),
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]
    return HistoryResponse(messages=messages)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Answer a user question within a chat session via the RAG pipeline.

    Args:
        request: The session id and user message.

    Returns:
        The generated answer and its source articles.

    Raises:
        HTTPException: 400 if session_id is not a valid UUID, 500 on pipeline failure.
    """
    try:
        session_uuid = uuid.UUID(request.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    try:
        result = ask(request.message, session_uuid)
    except Exception as e:
        logger.error(f"Chat pipeline failed for session {session_uuid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    sources = []
    if request.bypass_source_filter or not _should_hide_sources(result["answer"], result["sources"]):
        sources = []
        for s in result["sources"]:
            clean_title = _clean_title(s["title"])
            raw_url = s["url"] or ""
            sources.append(
                SourceOut(
                    title=clean_title,
                    source=_display_source(clean_title, s["source"]),
                    date=s["date"] or "",
                    score=s["score"],
                    # Only expose real, navigable URLs — ingestion paths for
                    # manually uploaded articles use synthetic
                    # "drive_reviewed://<filename>.pdf" placeholders that
                    # aren't a valid link destination.
                    url=raw_url if raw_url.startswith("http") else "",
                    article_id=s["article_id"],
                    content=s["chunk_text"] or "",
                )
            )
    return ChatResponse(
        answer=result["answer"],
        sources=sources,
        generation_failed=result.get("generation_failed", False),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
