"""FastAPI backend exposing the news RAG pipeline as an HTTP API for the React frontend."""
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from db import postgres
from rag.pipeline import ask

app = FastAPI(title="News RAG Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class SourceOut(BaseModel):
    title: str
    source: str
    date: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


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

    sources = [
        SourceOut(title=s["title"], source=s["source"], date=s["date"] or "", score=s["score"])
        for s in result["sources"]
    ]
    return ChatResponse(answer=result["answer"], sources=sources)
