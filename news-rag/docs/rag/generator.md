# Generator

`rag/generator.py`

## Model

By default, generation runs on **Llama 3.1** served locally by
[Ollama](https://ollama.com) (the `ollama` service in `docker-compose.yml`).
Ollama exposes an OpenAI-compatible `/v1/chat/completions` endpoint, so
`rag/generator.py` talks to it with the standard `openai` SDK, just pointed
at `OLLAMA_URL` (`config.py`) instead of `api.openai.com` — no API key or
external network call required. Change `OLLAMA_MODEL` in `.env` to use a
different pulled model (see
[Setup → Switching the Ollama model](../setup.md#switching-the-ollama-model)).

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

If the LLM call itself fails (Ollama not running, model not pulled, network
error, etc.), the exception is caught and logged, and a generic Indonesian
error message is returned instead of raising and crashing the chat session.
