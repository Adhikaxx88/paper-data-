# Generator

`rag/generator.py`

## Model

Generation runs on **[OpenRouter](https://openrouter.ai)** using the model in
`RAG_GENERATOR_MODEL` (default `deepseek/deepseek-chat-v3-0324`). `rag/generator.py`
uses the standard `openai` SDK pointed at `OPENROUTER_BASE_URL`
(`https://openrouter.ai/api/v1`), authenticated with `OPENROUTER_API_KEY`.
Change `RAG_GENERATOR_MODEL` in `.env` to switch models; no code change is needed.
The same model is used by the `/api/search` generator in
`backend/generation/generator.py`.

## System prompt template

```text
Anda adalah asisten berita yang menjawab pertanyaan HANYA berdasarkan konteks berita yang diberikan di bawah ini. Jangan menggunakan pengetahuan di luar konteks.

Aturan:
1. Jawab dalam Bahasa Indonesia, singkat dan jelas.
2. Selalu sertakan sumber (nama media dan tanggal) untuk klaim yang Anda buat.
3. Jika konteks yang diberikan tidak cukup untuk menjawab pertanyaan, katakan dengan jelas: "Maaf, tidak ditemukan informasi yang relevan untuk menjawab pertanyaan ini."
4. Jangan mengarang informasi yang tidak ada dalam konteks.
```

The retrieved chunks are formatted into a numbered context block
(`build_context_block`) and appended to the user's message, e.g.:

```text
Konteks berita:
[1] Sumber: Kompas.com | Tanggal: 2026-08-15 | Judul: OJK Perketat Aturan Pinjol
Otoritas Jasa Keuangan mengumumkan aturan baru...

[2] Sumber: CNBC Indonesia | Tanggal: 2026-08-14 | Judul: ...
...

Pertanyaan: <user's question>
```

## How conversation history is managed

`generate_answer(question, chunks, history)` receives `history` as a list of
`{"role": ..., "content": ...}` dicts already loaded from PostgreSQL by
[`rag/pipeline.py`](pipeline.md) (the last `CONVERSATION_HISTORY_LIMIT`
messages, default 10, oldest first). These are inserted as prior turns
between the system prompt and the current question, so the model sees the
conversation in order:

```
[system prompt]
[...history turns...]
[user: "Konteks berita: ... \n\nPertanyaan: <question>"]
```

The model is called with `temperature=0.2` to keep answers factual and
consistent rather than creative.

## Fallback behavior when no context is found

If `rag/retriever.py` returns no chunks (e.g. no Qdrant hits, or the
collection is empty), `build_context_block` inserts the placeholder text
`(Tidak ada konteks berita yang relevan ditemukan.)` instead of a numbered
list. Combined with rule 3 of the system prompt, this leads the model to
respond with the fixed fallback message rather than guessing:

> "Maaf, tidak ditemukan informasi yang relevan untuk menjawab pertanyaan
> ini."

If the LLM call itself fails (invalid or missing `OPENROUTER_API_KEY`, quota or
rate limit, unknown model slug, network error, etc.), the exception is caught and logged, and a generic Indonesian
error message is returned instead of raising and crashing the chat session.
