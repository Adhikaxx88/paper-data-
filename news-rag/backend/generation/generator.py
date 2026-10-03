"""Generate a grounded answer from search result chunks via OpenRouter (RAG_GENERATOR_MODEL)."""
import httpx
from loguru import logger

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, RAG_GENERATOR_MODEL, RAG_GENERATOR_PROVIDER, provider_body

_SYSTEM_EN = (
    "You are a research assistant for a study on child development and youth mental health in Indonesia. "
    "Answer the user's question based ONLY on the provided sources. "
    "Be concise (max 3 paragraphs). Cite sources as [Source N]. "
    "Do not mention information outside the provided sources. "
    "If the sources don't contain enough information, say so."
)

_SYSTEM_ID = (
    "Kamu adalah asisten riset untuk studi perkembangan anak dan kesehatan mental remaja di Indonesia. "
    "Jawab pertanyaan pengguna HANYA berdasarkan sumber yang diberikan. "
    "Jawab secara ringkas (maks 3 paragraf). Kutip sumber sebagai [Source N]. "
    "Jangan menyebut informasi di luar sumber yang diberikan. "
    "Jika sumber tidak cukup informatif, sampaikan hal tersebut."
)


def generate_answer(query: str, chunks: list[dict], detected_lang: str) -> str:
    """Generate a grounded answer to query from the top chunks via OpenRouter.

    Args:
        query: The user's (normalized) search query.
        chunks: Search result dicts (each with "title" and "chunk_text");
            only the first 5 are used as context.
        detected_lang: "id", "en", or "auto" — selects the system prompt
            language ("auto" defaults to Indonesian).

    Returns:
        The generated answer text, or "" if OpenRouter is unreachable or the
        request otherwise fails.
    """
    context = "\n\n".join(
        f"[Source {i + 1}] {c['title']}\n{c['chunk_text']}" for i, c in enumerate(chunks[:5])
    )

    system = _SYSTEM_EN if detected_lang == "en" else _SYSTEM_ID

    user_content = f"Sources:\n{context}\n\nQuestion: {query}\n\nAnswer:"

    try:
        response = httpx.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            json={
                "model": RAG_GENERATOR_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                **provider_body(RAG_GENERATOR_PROVIDER),
            },
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=60.0,
        )
        response.raise_for_status()
        return (response.json()["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        logger.warning(f"generate_answer failed: {e}")
        return ""
