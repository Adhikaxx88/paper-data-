# Evaluation

`evaluation/` has two scripts. `generate_dataset.py` builds a golden Q&A
dataset from the stored articles. `evaluate.py` replays that dataset through
the chatbot's HTTP API and scores the answers with RAGAS and DeepEval.

## Models per role

Three roles use three models, all served through OpenRouter. Keeping them
separate avoids a model grading its own output.

| Role | Config variable | Default model | Used by |
|---|---|---|---|
| Dataset generator | `DATASET_GENERATOR_MODEL` | `openai/gpt-4o-mini` | `evaluation/generate_dataset.py` |
| RAG generator (system under test) | `RAG_GENERATOR_MODEL` | `deepseek/deepseek-chat-v3-0324` | `rag/generator.py`, `/api/chat`, `/api/search` |
| Judge (RAGAS and DeepEval) | `JUDGE_MODEL` | `google/gemini-2.5-flash` | `evaluation/evaluate.py` |

`answer_relevancy` embeds text locally with `sentence-transformers/all-MiniLM-L6-v2`.
No other model is used for scoring.

**Provider pinning.** Each role has a provider slug (`DATASET_GENERATOR_PROVIDER`,
`RAG_GENERATOR_PROVIDER`, `JUDGE_PROVIDER`, `GUARDRAIL_PROVIDER`). A non-empty
slug is sent as OpenRouter's `provider.order` with `allow_fallbacks: false`
(`config.py:provider_body`), so a request fails instead of moving to another
host. An empty value means unpinned. `evaluate.py` logs a warning for an
unpinned role.

**Guardrail model.** `GUARDRAIL_MODEL` runs `scope_check` and `language_detect`
in `/api/search` only. `/api/chat` does not run these guardrails, so the
guardrail model does not change RAGAS or DeepEval scores.

Every `results.csv` row carries `generator_model`, `generator_provider`,
`judge_model`, and `judge_provider`. The dataset CSV carries `dataset_model`
and `dataset_provider`.

## `generate_dataset.py`: building the golden dataset

Reads every row of `clean_articles` (both `web_scraping` and `pdf_knowledge`
sources) and asks `DATASET_GENERATOR_MODEL` for Q&A pairs in Indonesian. The
prompt asks for answers drawn strictly from the article text.

| Constant | Value | Effect |
|---|---|---|
| `TARGET_TOTAL_QUESTIONS` | `2500` | Total pairs. Quotas per `topic_category` are proportional to article counts. |
| `MIN_CONTENT_LENGTH` | `500` | Shorter articles are skipped. |
| `EXCLUDED_CATEGORIES` | `{"additional"}` | Categories left out of the dataset. |
| `REQUEST_DELAY_SEC` | `0.75` | Fixed delay between calls. |
| `MAX_RETRIES` / `BACKOFF_BASE_SEC` | `4` / `2` | Exponential backoff on HTTP 429. |

The model returns `{"pairs": [...]}` (`response_format: json_object`). A plain
`Q:` / `A:` text parser handles models that ignore the format.

Output: `evaluation/golden_dataset_openrouter.csv` with columns `question,
ground_truth, article_id, source_title, source, topic_category, source_type,
dataset_model, dataset_provider`. The earlier Ollama dataset
`golden_dataset.csv` is kept for comparison.

| Command | Effect |
|---|---|
| `docker compose run evaluation python evaluation/generate_dataset.py` | Generates the dataset inside Docker. Needs PostgreSQL and `OPENROUTER_API_KEY`. |
| `python evaluation/generate_dataset.py --local` | Loads `evaluation/.env.local` (localhost-mapped ports). Also used automatically when the `postgres` hostname does not resolve. |
| `python evaluation/generate_dataset.py --plan-only` | Prints the distribution and cost estimate. Makes no API calls. |

## `evaluate.py`: scoring the chatbot

Entry point: `python -m evaluation.evaluate`. It runs from the host or in
the `evaluation` compose service, as long as the backend is reachable at
`EVAL_CHAT_API_BASE`.

### Pipeline

1. **Collect.** For each row in the dataset, `query_chat_api()` opens a new
   session (`POST /api/session`) and asks the question (`POST /api/chat`).
   A new session per question keeps earlier rows out of the conversation
   history. The `answer` and the `content` of every returned source (as
   `contexts`) are kept.
2. **RAGAS.** `run_ragas()` scores `faithfulness`, `answer_relevancy`,
   `context_precision`, and `context_recall` (see below).
3. **DeepEval.** `run_deepeval_hallucination()` runs `HallucinationMetric`
   once per row (see below).
4. **Write.** RAGAS scores, DeepEval scores, and the metadata columns are
   merged into `results.csv`, and the mean of each metric is printed.

Steps 2 to 4 run only after step 1 has finished for every row.

### RAGAS metrics

| Metric | Reference needed | What it measures |
|---|---|---|
| `faithfulness` | no | Whether the answer's claims follow from the retrieved contexts. |
| `answer_relevancy` | no | Whether the answer addresses the question. Uses local embeddings. |
| `context_precision` | yes (`ground_truth`) | Whether the retrieved contexts are relevant to the reference answer. |
| `context_recall` | yes (`ground_truth`) | Whether the retrieved contexts contain what the reference answer needs. |

- Judge: `JUDGE_MODEL` through `langchain_openai.ChatOpenAI`, `temperature=0`,
  with `JUDGE_PROVIDER` pinned.
- `RunConfig`: `max_workers=1`, `timeout=600`, `max_retries=3`, `max_wait=60`.
- `raise_exceptions=True`, so a judge or parse error is an exception, not a
  silent NaN.
- **Parallel rows.** Rows are scored by a process pool of `EVAL_MAX_WORKERS`
  worker processes (`spawn` start method). Each process runs one row at a time
  on its main thread, with a fresh judge LLM and fresh metric objects per row.
  Thread-based parallelism failed in testing (`asyncio` event-loop errors, and
  `LLM is not set` from shared metric state), so the process pool is the
  supported path.
- **Retry.** `with_retry()` wraps each row: 2 attempts, 5 s wait with up to 30%
  jitter. HTTP 401 and 402 stop the run at once (`EvalAborted`). After 20
  consecutive permanent failures the run stops too.

### Row handling in RAGAS

| Case | Stored in `checkpoint.json` | Metrics |
|---|---|---|
| Scored | yes, with `user_input` and `response` | numbers |
| Collect failed (empty answer or no contexts) | yes, with `skipped: true` | NaN, not judged |
| Permanent failure after retries | no | NaN in the final frame; logged in `failed_rows.json` |

Scores that are NaN are never written to the checkpoint. After a permanent
failure, later rows are still scored and kept in memory, but they are not
written to `checkpoint.json` until the run is resumed. A resume therefore
re-scores from the first failed row onward.

### DeepEval `hallucination_grounded`

- `HallucinationMetric(model=judge, threshold=0.5)`, judged by `JUDGE_MODEL`
  through the `OpenRouterJudge` adapter (`DeepEvalBaseLLM`).
- The column is named `hallucination_grounded`. Per the code docstring, higher
  is better and 1 means the answer is fully grounded in the contexts.
- Rows with no contexts get `None` and are not judged.
- Failures are per row: a failed row becomes `None`, and the run continues.
  The log ends with a `DeepEval summary` line.
- Rows run in a thread pool of `EVAL_MAX_WORKERS`. Each call creates its own
  metric instance.
- Scores are cached per row in `deepeval_checkpoint.json`, keyed by row
  index. A cached entry is reused only if its `question` and `answer` still
  match.

### Output: `results.csv`

One row per dataset row. Columns:

| Column group | Columns |
|---|---|
| Dataset | `question`, `ground_truth`, `article_id`, `source_title`, `source`, `topic_category`, `source_type`, `dataset_model`, `dataset_provider` |
| Collect | `answer`, `contexts` |
| RAGAS | `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall` |
| DeepEval | `hallucination_grounded` |
| Run metadata | `generator_model`, `generator_provider`, `judge_model`, `judge_provider` |

The printed summary shows the mean of each metric, the count of missing values
per metric, and the count of rows with at least one missing metric. Collect-failed
rows (empty answer) are excluded from the means.

### Run directory and files

`RUN_DIR` defaults to `evaluation/`. Set `EVAL_RUN_DIR` to write to a separate
folder, for example for a pilot run.

| File | Written by | Purpose |
|---|---|---|
| `rag_outputs_checkpoint.json` | collect | Answers and contexts per question. A cached answer is reused only if its stored question matches the row. Otherwise the log shows `Cache mismatch, re-querying`. |
| `checkpoint.json` | RAGAS | Scored rows, in dataset order (see the row-handling table). |
| `deepeval_checkpoint.json` | DeepEval | Per-row hallucination scores. |
| `failed_rows.json` | `main()` | Permanent failures for this run. Rewritten on every exit, including aborts. |
| `results.csv` | `_run_evaluation()` | Final merged output. |

To start a fresh run, for example after changing a judge or generator model,
delete the checkpoint files in the run directory.

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `EVAL_DATASET_PATH` | `evaluation/golden_dataset_openrouter.csv` | Dataset to evaluate. |
| `EVAL_RUN_DIR` | `evaluation/` | Folder for checkpoints, `failed_rows.json`, and `results.csv`. |
| `EVAL_CHAT_API_BASE` | `http://localhost:8000` | Backend base URL. Use `http://localhost:8686` for the backend published by Docker Compose. |
| `EVAL_MAX_WORKERS` | `1` | Parallel workers: RAGAS processes and DeepEval threads. Raise it only after checking backend load and judge rate limits. |

### Commands

```bash
# Host (backend running natively on port 8000, or set EVAL_CHAT_API_BASE)
python -m evaluation.evaluate

# Backend from docker compose (published on host port 8686)
EVAL_CHAT_API_BASE=http://localhost:8686 python -m evaluation.evaluate
```

PowerShell:

```powershell
$env:EVAL_CHAT_API_BASE = "http://localhost:8686"
python -m evaluation.evaluate
```

Inside Docker (the `evaluation` service is in the `evaluation` profile):

```bash
docker compose run --rm -e EVAL_CHAT_API_BASE=http://backend:8000 evaluation python -m evaluation.evaluate
```

Inside the compose network the backend is `backend:8000`, not the host port.
Without the `-e` flag the container would try `localhost:8000` and fail.

## Dependencies

`ragas==0.2.15`, `langchain-community<0.4`, `deepeval`, `langchain-openai`,
`langchain-huggingface`, `datasets`, `openai`, and `pandas` are listed in the
root `requirements.txt`. Install with `pip install -r requirements.txt`.
