"""Search API: guardrailed hybrid search over the news chunk collection."""
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from backend.generation.generator import generate_answer
from backend.guardrails.input import run_input_guardrails
from backend.guardrails.output import protect_output
from backend.retrieval.searcher import get_dense_model, hybrid_search
from backend.session import append_to_session, get_history, get_or_create_session
from config import CONVERSATION_HISTORY_LIMIT, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, RETRIEVAL_TOP_K
from vectorization.qdrant_store import get_client

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500)
    top_k: int = Field(default=RETRIEVAL_TOP_K, ge=1, le=50)
    conversation_history: list[str] = Field(default=[])
    session_id: str = Field(default="")


class ResultItem(BaseModel):
    title: str
    url: str
    keyword: str
    language: str
    chunk_text: str
    chunk_index: int
    article_id: str  # md5 hash


class SearchResponse(BaseModel):
    results: list[ResultItem]
    guardrail_checks: list[dict]
    query_normalized: str
    session_id: str
    total_results: int
    answer: str  # generated answer, "" if failed
    detected_lang: str  # "id", "en", or "auto"


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    """Run input guardrails, hybrid search, and output protection for a query.

    Args:
        request: The search query, top_k, session id, and any client-side
            conversation history (merged with server-side session history
            for the multi-turn guardrail check).

    Returns:
        SearchResponse on success.

    Returns (as a 400 JSONResponse instead of raising):
        {"error": "guardrail_rejection", "check": <name>, "reason": <reason>,
         "checks_passed": [<names of checks that passed before the failure>]}
    """
    session = get_or_create_session(request.session_id)
    history = (get_history(session.session_id) or request.conversation_history)[-CONVERSATION_HISTORY_LIMIT:]

    normalized_query, checks, detected_lang = run_input_guardrails(request.query, history)

    failed = next((c for c in checks if not c.passed), None)
    if failed is not None:
        checks_passed = [c.check_name for c in checks if c.passed]
        logger.warning(f"Query rejected by guardrail '{failed.check_name}': {failed.reason}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "guardrail_rejection",
                "check": failed.check_name,
                "reason": failed.reason,
                "checks_passed": checks_passed,
            },
        )

    append_to_session(session.session_id, request.query)

    # No language filter — hybrid_search stays language-agnostic; detected_lang
    # only steers which language generate_answer replies in.
    raw_results = hybrid_search(normalized_query, top_k=request.top_k)
    results = protect_output(raw_results)
    answer = generate_answer(normalized_query, results, detected_lang)

    return SearchResponse(
        results=[ResultItem(**r) for r in results],
        guardrail_checks=[{"check_name": c.check_name, "passed": c.passed, "reason": c.reason} for c in checks],
        query_normalized=normalized_query,
        session_id=session.session_id,
        total_results=len(results),
        answer=answer,
        detected_lang=detected_lang,
    )


@router.get("/health")
def health():
    """Ping Qdrant and OpenRouter and report whether the dense model is loaded.

    The OpenRouter check calls GET /auth/key, so it also confirms that
    OPENROUTER_API_KEY is accepted, not just that the host is reachable.

    Returns:
        {"status": "ok", "qdrant": bool, "openrouter": bool, "model_loaded": bool}
    """
    qdrant_ok = False
    try:
        get_client().get_collections()
        qdrant_ok = True
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")

    openrouter_ok = False
    try:
        response = httpx.get(
            f"{OPENROUTER_BASE_URL}/auth/key",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=3.0,
        )
        openrouter_ok = response.status_code == 200
    except httpx.HTTPError as e:
        logger.warning(f"OpenRouter health check failed: {e}")

    model_loaded = get_dense_model() is not None

    return {
        "status": "ok",
        "qdrant": qdrant_ok,
        "openrouter": openrouter_ok,
        "model_loaded": model_loaded,
    }
