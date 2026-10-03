# Evaluation

`evaluation/` has two scripts: one generates a golden Q&A dataset from the
scraped articles, the other replays that dataset through the live chatbot
and scores the results with RAGAS and DeepEval.

Three roles use three different models, all served through OpenRouter. Keeping
them separate avoids a model grading its own output and makes the setup easy
to describe in the paper:

| Role | Config variable | Default model | Used by |
|---|---|---|---|
| Dataset generator | `DATASET_GENERATOR_MODEL` | `openai/gpt-4o-mini` | `generate_dataset.py` |
| RAG generator (system under test) | `RAG_GENERATOR_MODEL` | `deepseek/deepseek-chat-v3-0324` | `rag/generator.py`, `/api/chat`, `/api/search` |
| Judge (RAGAS + DeepEval) | `JUDGE_MODEL` | `google/gemini-2.5-flash` | `evaluate.py` |

Each `results.csv` row carries `generator_model`, `generator_provider`,
`judge_model`, and `judge_provider` columns, so every reported number can be
traced back to the model and the provider that served it. The dataset file has
`dataset_model` and `dataset_provider` columns for the same reason.

**Provider pinning.** OpenRouter may serve the same model slug from several
hosts, and each host can differ in quantization, speed, and behavior. Each role
therefore sets a provider slug (`RAG_GENERATOR_PROVIDER`, `JUDGE_PROVIDER`,
`DATASET_GENERATOR_PROVIDER`, `GUARDRAIL_PROVIDER`) that is sent as OpenRouter's
`provider.order` with `allow_fallbacks: false`. If the pinned host is down, the
request fails rather than silently moving to another host. An empty value means
"unpinned", which is recorded as `unpinned` in the CSV and logged as a warning.

**Guardrail model (not an evaluation role).** `GUARDRAIL_MODEL` runs
`scope_check` and `language_detect` in `/api/search`. `evaluate.py` calls
`/api/chat`, which does not run these guardrails, so the guardrail model does
not affect RAGAS or DeepEval scores directly. Its only effect is which queries
reach the system. Report it separately in the methodology.

## `generate_dataset.py` — building the golden dataset

Samples up to `ARTICLES_PER_SOURCE` (5) of the longest `clean_articles`
rows per distinct `source`, capped at `MAX_ARTICLES_TOTAL` (50) overall, and
asks `DATASET_GENERATOR_MODEL` to write 2-3 Indonesian question/answer pairs
per article — mixing factual, practical, situational, and statistical
question phrasings, and instructed to answer strictly from the article's own
content. The model is asked for a JSON object `{"pairs": [...]}`
(`response_format: json_object`), and a plain-text `Q:/A:` fallback parser
handles models that ignore the format.

Output is written to `evaluation/golden_dataset_openrouter.csv` with columns
`question, ground_truth, article_id, source_title, source, dataset_model`.
The earlier Ollama-generated `golden_dataset.csv` is kept for comparison.

Run it inside Docker (needs PostgreSQL and `OPENROUTER_API_KEY` in `.env`):

```bash
docker compose run evaluation python evaluation/generate_dataset.py
```

or outside Docker with `--local` (or automatically, if the `postgres`
hostname doesn't resolve) to load `evaluation/.env.local`'s
localhost-mapped ports instead of the in-network service names:

```bash
python evaluation/generate_dataset.py --local
```

## `evaluate.py` — scoring the chatbot

Runs from outside Docker. It reads the OpenRouter settings from `.env` (via
`config.py`) and calls the backend's HTTP API at `http://localhost:8000` (the
host-published port for the `backend` service), so the backend can be running
either in Docker or natively.

For every row in `evaluation/golden_dataset_openrouter.csv`:

1. Opens a fresh session (`POST /api/session`) and asks the question
   (`POST /api/chat`) — a new session per question so answers aren't
   influenced by prior rows' conversation history.
2. Collects the generated `answer` and the `content` text of every
   returned source as `contexts` (see [api.md#post-apichat](api.md#post-apichat)
   for why `/api/chat`'s `SourceOut` carries a `content` field at all).
3. Builds a RAGAS `EvaluationDataset` from `(question, answer, contexts,
   ground_truth)` and runs:
   - **`faithfulness`** — does the answer's claims follow from the
     retrieved contexts?
   - **`answer_relevancy`** — reference-free: does the answer actually
     address the question?
   - **`context_precision`** / **`context_recall`** — reference-based
     (uses `ground_truth`): are the retrieved contexts relevant and
     sufficient to produce that ground-truth answer?

   The judge LLM is `JUDGE_MODEL` on OpenRouter, wrapped for RAGAS with
   `langchain_openai.ChatOpenAI` (`temperature=0`). The embeddings used for
   `answer_relevancy` stay local (`sentence-transformers/all-MiniLM-L6-v2`).
   `raise_exceptions=True` is set, so judge or parse failures stop the run
   instead of producing silent NaN rows.
4. Runs DeepEval's `HallucinationMetric` per row against the same
   `contexts`, via a small `DeepEvalBaseLLM` adapter (`OpenRouterJudge`) that
   wraps the OpenAI-compatible client pointed at OpenRouter, with the same
   `JUDGE_MODEL`.
5. Merges everything into one DataFrame, adds `generator_model` and
   `judge_model` columns, writes `evaluation/results.csv`, then prints the
   mean of each metric column together with the model names.

```bash
python -m evaluation.evaluate
```

Checkpoints (`evaluation/rag_outputs_checkpoint.json` and
`evaluation/checkpoint.json`) are stored by absolute path next to the script,
so they're found no matter which directory the script is launched from.

Each cached entry stores the question it was produced for:

- **RAG answers:** a cached answer is reused only when its stored question
  matches the current row. Otherwise the row is re-queried and the log shows
  `Cache mismatch, re-querying`.
- **RAGAS scores:** cached rows are reused only while their stored question and
  answer still match the current dataset, starting from the first row. Rows
  from the first mismatch onward are discarded and re-scored.

Deleting the checkpoints is still the cleanest way to start a fresh run, for
example after changing a judge or generator model.

**Failure reporting.** RAGAS is run with `raise_exceptions=True`, so a judge
or parse failure stops the run immediately. DeepEval fails per row: a failed
row is recorded as `None`, and the run continues. At the end, the log prints a
`DeepEval summary` line with the counts of failed, skipped (no contexts), and
scored rows. The printed summary also reports how many rows are missing each
metric and how many have at least one missing metric.

Rows where retrieval returned no sources (`contexts` empty) skip the
hallucination check (there's nothing to check groundedness against) and
record a `None` score rather than a misleading 0 or 1.

## Dependencies

`ragas`, `deepeval`, `langchain-openai`, `langchain-huggingface`, `datasets`,
`openai`, and `pandas` are listed in the root `requirements.txt` alongside the rest of the pipeline's dependencies —
install with `pip install -r requirements.txt` same as everything else.
