"""Generate chatbot answers from retrieved context and conversation history using GPT-4o-mini."""
from typing import Any, Optional

from loguru import logger
from openai import OpenAI

from config import LLM_MODEL, OPENAI_API_KEY

SYSTEM_PROMPT = """Anda adalah asisten berita yang menjawab pertanyaan HANYA berdasarkan konteks \
berita yang diberikan di bawah ini. Jangan menggunakan pengetahuan di luar konteks.

Aturan:
1. Jawab dalam Bahasa Indonesia, singkat dan jelas.
2. Selalu sertakan sumber (nama media dan tanggal) untuk klaim yang Anda buat.
3. Jika konteks yang diberikan tidak cukup untuk menjawab pertanyaan, katakan dengan jelas: \
"Maaf, tidak ditemukan informasi yang relevan untuk menjawab pertanyaan ini."
4. Jangan mengarang informasi yang tidak ada dalam konteks."""

_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Return a lazily-initialized, module-level OpenAI client.

    Returns:
        A configured OpenAI client instance.
    """
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def build_context_block(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a numbered context block for the prompt.

    Args:
        chunks: Retrieved chunk dicts from rag.retriever.retrieve.

    Returns:
        A formatted string listing each source with its text.
    """
    if not chunks:
        return "(Tidak ada konteks berita yang relevan ditemukan.)"

    blocks = [
        f"[{i}] Sumber: {c['source']} | Tanggal: {c['date']} | Judul: {c['title']}\n{c['chunk_text']}"
        for i, c in enumerate(chunks, start=1)
    ]
    return "\n\n".join(blocks)


def build_messages(
    question: str, chunks: list[dict[str, Any]], history: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Assemble the full chat messages payload for the LLM call.

    Args:
        question: The current user question.
        chunks: Retrieved context chunks.
        history: Prior conversation turns, each a dict with role and content.

    Returns:
        List of message dicts ready to pass to the OpenAI chat completions API.
    """
    context_block = build_context_block(chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": h["role"], "content": h["content"]} for h in history)
    messages.append(
        {
            "role": "user",
            "content": f"Konteks berita:\n{context_block}\n\nPertanyaan: {question}",
        }
    )
    return messages


def generate_answer(question: str, chunks: list[dict[str, Any]], history: list[dict[str, str]]) -> str:
    """Call GPT-4o-mini to produce an answer grounded in the retrieved context.

    Args:
        question: The current user question.
        chunks: Retrieved context chunks from the retriever.
        history: Prior conversation turns for multi-turn continuity.

    Returns:
        The generated answer text.
    """
    messages = build_messages(question, chunks, history)
    try:
        response = get_openai_client().chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return "Maaf, terjadi kesalahan saat menghasilkan jawaban. Silakan coba lagi."
