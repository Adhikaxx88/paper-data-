# Generation

`generate_answer()` in `backend/generation/generator.py` produces the
`answer` field of `SearchResponse`. It runs **after** guardrails, retrieval,
and output protection — it only ever sees results that already passed
`protect_output()` (truncated to 500 chars, redacted, field-allowlisted).

## Where it fits

```
run_input_guardrails() → hybrid_search() → rerank() → protect_output() → generate_answer()
  (guardrails/input.py)   (retrieval/searcher.py, RRF)   ↑ cross-encoder    (guardrails/output.py)  (generation/generator.py)
                                                    (retrieval/searcher.py)
```

`rerank()` runs *inside* `hybrid_search()` (not a separate call from
`backend/routers/search.py`) — by the time `generate_answer()`'s caller
gets `results` back from `hybrid_search()`, they're already cross-encoder
reranked, not just RRF-fused. See [retrieval.md#reranking-cross-encoder-bge-reranker-v2-m3](retrieval.md#reranking-cross-encoder-bge-reranker-v2-m3).

Called from `backend/routers/search.py`:

```python
raw_results = hybrid_search(normalized_query, top_k=request.top_k)
results = protect_output(raw_results)
answer = generate_answer(normalized_query, results, detected_lang)
```

## Context: top-5 chunks

```python
context = "\n\n".join(
    f"[Source {i + 1}] {c['title']}\n{c['chunk_text']}" for i, c in enumerate(chunks[:5])
)
```

Even if `top_k` (and therefore `results`) is larger, only the **first 5**
results are used as generation context — they're already ranked best-first
by the cross-encoder reranker (not just RRF fusion), so this keeps the
prompt bounded regardless of `top_k` without losing the strongest matches.
Because reranking scores the query against each chunk directly (rather than
RRF's rank-based fusion of two independent similarity lists), this top-5
context is higher-quality — more reliably the actually-most-relevant
chunks — than it would be straight off RRF. Each is labeled `[Source N]` so
the model can cite it directly in the answer, and the same `[Source N]`
numbering is what the frontend's `ChatMessage` sources list uses.

## Language detection (`language_detect` guardrail)

`detected_lang` doesn't come from `generate_answer()` itself — it's
produced earlier by the `language_detect` guardrail check
(`backend/guardrails/input.py`), which only runs after every other
guardrail check has passed (see [guardrails.md](guardrails.md#6-language_detect)):

1. Prompts the guardrail LLM (`GUARDRAIL_MODEL` via OpenRouter) to classify the
   query as `"id"` or `"en"` with a `confidence` score, expecting JSON like
   `{"language": "id", "confidence": 0.95}`.
2. Extracts the first `{...}` block from the raw response with a regex
   (tolerates the model wrapping JSON in extra prose) and parses it.
3. Accepts the detected language **only if `confidence >= 0.75`** and it's
   one of `"id"`/`"en"`; otherwise falls back to `"auto"`.
4. Falls back to `"auto"` on any error too — unreachable OpenRouter, timeout,
   HTTP error, unparseable response — and logs a WARNING.

`detected_lang` is threaded through unchanged from the guardrail result to
`generate_answer()`.

## System prompt switching

```python
system = _SYSTEM_EN if detected_lang == "en" else _SYSTEM_ID
```

`"en"` gets the English system prompt; **everything else — `"id"` or
`"auto"` — gets the Indonesian one.** `"auto"` defaulting to Indonesian
matches the project's primary audience (Indonesian youth mental health
research) rather than defaulting to English.

Both prompts instruct the model to:
- answer **only** from the provided sources (no outside knowledge),
- stay concise (max 3 paragraphs),
- cite sources as `[Source N]`,
- explicitly say so if the sources don't have enough information.

## Prompt assembly and the OpenRouter call

```python
user_content = f"Sources:\n{context}\n\nQuestion: {query}\n\nAnswer:"

response = httpx.post(
    f"{OPENROUTER_BASE_URL}/chat/completions",
    json={
        "model": RAG_GENERATOR_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    },
    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
    timeout=60.0,
)
response.raise_for_status()
return (response.json()["choices"][0]["message"]["content"] or "").strip()
```

The system prompt is sent as a separate `system` message, and the sources and
question go in the `user` message. The response is free-form text, so no
JSON mode is requested. The timeout is 60s (vs. 15s for the guardrail LLM
calls), since generation with context is slower than a short classification call.

`OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY`, and `RAG_GENERATOR_MODEL` come from
`config.py`, which is the single source of truth. The `/api/search` generator
here, the `/api/chat` generator in `rag/generator.py`, and the Streamlit app all
use `RAG_GENERATOR_MODEL`. The guardrail calls use `GUARDRAIL_MODEL` instead.
See [quickstart.md](quickstart.md#env-vars).

## Fail-open behavior

`generate_answer()` wraps the entire OpenRouter call in a bare `except
Exception`, logs a warning via loguru, and returns `""` on **any** failure
— invalid or missing key, quota or rate limit, unknown model slug, timeout,
malformed response, etc.
It never raises, so a `/api/search` request always returns a `200` with
full `results` even if generation fails entirely; only `answer` is affected
(empty string). The frontend's `ChatMessage` component renders `"Sources
found, no summary generated."` when `answer` is `""` but `results` is
non-empty, rather than showing a blank assistant message. See
[frontend.md](frontend.md).
