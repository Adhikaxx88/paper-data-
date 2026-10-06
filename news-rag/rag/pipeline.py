"""Orchestrate retrieval + generation and persist chat history per session."""
import uuid
from typing import Any, Optional

from loguru import logger

from config import CONVERSATION_HISTORY_LIMIT
from db import postgres
from rag.generator import generate_answer
from rag.retriever import retrieve


def ask(question: str, session_id: uuid.UUID) -> dict[str, Any]:
    """Answer a user question within a chat session, persisting both turns.

    Args:
        question: The user's natural-language question.
        session_id: UUID of the chat session, used to load history and save turns.

    Returns:
        Dict with keys "answer" (str) and "sources" (list of retrieved chunk dicts).
    """
    postgres.create_session(session_id)
    history = postgres.get_recent_messages(session_id, CONVERSATION_HISTORY_LIMIT)

    postgres.insert_message(session_id, "user", question)

    chunks = retrieve(question)
    answer, generation_failed = generate_answer(question, chunks, history)

    postgres.insert_message(session_id, "assistant", answer)
    logger.info(f"Session {session_id}: answered question with {len(chunks)} sources")

    return {"answer": answer, "sources": chunks, "generation_failed": generation_failed}
