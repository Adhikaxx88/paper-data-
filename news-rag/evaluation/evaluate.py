"""Evaluate the RAG chatbot against the golden dataset with RAGAS + DeepEval.

Runs from the host (outside Docker). Loads the OpenRouter settings from the
project .env (via config.py) and hits the backend's HTTP API at localhost:8000
(the port docker-compose.yml publishes the "backend" service on), so it works
the same way whether the backend runs in Docker or on the host.

For each question in evaluation/golden_dataset_openrouter.csv, opens a fresh chat
session and posts to /api/chat to get the generated answer and retrieved
chunk texts, then scores the (question, answer, contexts, ground_truth)
tuples with:
  - RAGAS: faithfulness, answer_relevancy, context_precision, context_recall
  - DeepEval: HallucinationMetric

Both metric suites use JUDGE_MODEL on OpenRouter as the judge LLM. The
embeddings used by RAGAS (answer_relevancy) stay local (all-MiniLM-L6-v2).

Results are written to evaluation/results.csv, tagged with the generator and
judge model names, and summary means are printed.

Run with: python -m evaluation.evaluate
"""
import json
import math
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from loguru import logger
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env.local", override=True)
load_dotenv()

from config import (  # noqa: E402
    DATASET_GENERATOR_MODEL,
    DATASET_GENERATOR_PROVIDER,
    JUDGE_MODEL,
    JUDGE_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    RAG_GENERATOR_MODEL,
    RAG_GENERATOR_PROVIDER,
    provider_body,
)

EVAL_DIR = Path(__file__).resolve().parent
# Absolute paths so checkpoints land in the same place no matter which
# directory this script is launched from.
# Overridable via env so a pilot run can use its own dataset and output folder
# without touching the full run's checkpoints (e.g. EVAL_RUN_DIR=/app/evaluation/runs/pilot30).
DATASET_PATH = Path(os.getenv("EVAL_DATASET_PATH", EVAL_DIR / "golden_dataset_openrouter.csv"))
RUN_DIR = Path(os.getenv("EVAL_RUN_DIR", EVAL_DIR))
RUN_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = RUN_DIR / "checkpoint.json"
RAG_CHECKPOINT_FILE = RUN_DIR / "rag_outputs_checkpoint.json"
DEEPEVAL_CHECKPOINT_FILE = RUN_DIR / "deepeval_checkpoint.json"
RESULTS_PATH = RUN_DIR / "results.csv"
CHAT_API_BASE = os.getenv("EVAL_CHAT_API_BASE", "http://localhost:8000")
REQUEST_TIMEOUT = 300
# Parallel workers for chat-API collection and DeepEval scoring. Default 1 keeps
# the original sequential behaviour; raise it only after checking backend load.
EVAL_MAX_WORKERS = max(1, int(os.getenv("EVAL_MAX_WORKERS", "1")))

# Retry policy. Row-level retry is only a fallback: RAGAS already retries
# internally, and each row-level attempt repeats ~25 judge calls, so it stays at 2.
ROW_MAX_ATTEMPTS = 2
ROW_RETRY_WAIT = 5  # seconds before the retry, plus 0-30% jitter
# Collect (/api/chat) is cheap to repeat, so it gets more attempts than the judge rows.
CHAT_MAX_ATTEMPTS = 4
CHAT_RETRY_WAITS = [5, 15, 45]  # seconds before attempts 2, 3, 4; jitter applied on top
RAGAS_MAX_RETRIES = 3
RAGAS_MAX_WAIT = 60
CONSECUTIVE_FAILURE_LIMIT = 20
FATAL_STATUS_CODES = {401, 402}  # bad key or no credits: stop at once
METRIC_COLS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

FAILED_ROWS: list[dict] = []
_guard_lock = threading.Lock()
_consecutive_failures = 0


class EvalAborted(RuntimeError):
    """Stops the whole run: a fatal status code or too many failures in a row."""


def _status_code(exc: Exception) -> int | None:
    for obj in (exc, getattr(exc, "response", None)):
        code = getattr(obj, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _retry_after(exc: Exception) -> float | None:
    """Seconds from a Retry-After header on the exception's response, if any."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        return float(headers["Retry-After"])
    except (KeyError, TypeError, ValueError):
        return None


def with_retry(fn, label: str, max_attempts: int = ROW_MAX_ATTEMPTS, waits: list[float] | None = None):
    """Run fn up to max_attempts times with jittered backoff; honours Retry-After.

    waits[i] is the sleep before attempt i+2; without it, ROW_RETRY_WAIT is used.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except EvalAborted:
            raise
        except Exception as e:
            code = _status_code(e)
            if code in FATAL_STATUS_CODES:
                raise EvalAborted(f"fatal HTTP {code} on {label}: {e}") from e
            if attempt == max_attempts:
                raise
            wait = waits[attempt - 1] if waits else ROW_RETRY_WAIT
            retry_after = _retry_after(e)
            if retry_after is not None:
                wait = max(wait, retry_after)
            wait *= 1 + random.uniform(0, 0.30)
            # The message carries the status (e.g. 429), so the cause is countable in the log.
            logger.warning(
                f"retry {attempt}/{max_attempts - 1} for {label}: "
                f"{type(e).__name__}: {e}; sleeping {wait:.1f}s"
            )
            time.sleep(wait)


def has_nan(record: dict, keys: list[str]) -> bool:
    return any(record.get(k) is None or math.isnan(float(record[k])) for k in keys)


def _valid_score(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and not math.isnan(x)


def record_success() -> None:
    global _consecutive_failures
    with _guard_lock:
        _consecutive_failures = 0


def record_failure(phase: str, key, exc: Exception) -> None:
    """Log a permanently failed row; abort the run after too many in a row."""
    global _consecutive_failures
    with _guard_lock:
        FAILED_ROWS.append({"phase": phase, "key": str(key), "error": f"{type(exc).__name__}: {exc}"})
        _consecutive_failures += 1
        streak = _consecutive_failures
    logger.error(f"FAILED after retries [{phase}] {key}: {exc} (consecutive: {streak})")
    if streak >= CONSECUTIVE_FAILURE_LIMIT:
        raise EvalAborted(f"{streak} consecutive failures; last was {phase} {key}")


def write_failed_rows() -> None:
    with open(RUN_DIR / "failed_rows.json", "w", encoding="utf-8") as f:
        json.dump(FAILED_ROWS, f, ensure_ascii=False, indent=2)


def save_checkpoint(results: list, idx: int):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"results": results, "last_idx": idx}, f)


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"results": [], "last_idx": -1}


def load_golden_dataset() -> pd.DataFrame:
    """Load the golden Q&A dataset generated by generate_dataset.py.

    Returns:
        DataFrame with question, ground_truth, article_id, source_title, source.
    """
    df = pd.read_csv(DATASET_PATH)
    logger.info(f"Loaded {len(df)} golden Q&A pairs from {DATASET_PATH}")
    return df


def query_chat_api(question: str) -> dict[str, Any]:
    """Open a fresh chat session and ask the RAG pipeline one question.

    A new session is created per question so answers aren't influenced by
    conversation history from previous evaluation rows.

    Args:
        question: The user question to ask.

    Returns:
        Dict with "answer" (str) and "contexts" (list of retrieved chunk texts).
    """
    session_resp = requests.post(f"{CHAT_API_BASE}/api/session", timeout=REQUEST_TIMEOUT)
    session_resp.raise_for_status()
    session_id = session_resp.json()["session_id"]

    chat_resp = requests.post(
        f"{CHAT_API_BASE}/api/chat",
        # Raw retrieved chunks, not the UI-filtered list (see _should_hide_sources).
        json={"session_id": session_id, "message": question, "bypass_source_filter": True},
        timeout=REQUEST_TIMEOUT,
    )
    chat_resp.raise_for_status()
    payload = chat_resp.json()

    contexts = [s["content"] for s in payload["sources"] if s.get("content")]
    # Missing field = older backend without the flag, treated as not failed.
    return {
        "answer": payload["answer"],
        "contexts": contexts,
        "generation_failed": bool(payload.get("generation_failed", False)),
    }


def _chat_once(question: str) -> dict[str, Any]:
    result = query_chat_api(question)
    # The backend returns the apology text with HTTP 200 on LLM errors; retry it
    # instead of judging the apology as an answer.
    if result["generation_failed"]:
        raise RuntimeError("backend reported generation_failed=true")
    if not result["answer"]:
        raise ValueError("empty answer")
    return result


def collect_rag_outputs(df: pd.DataFrame) -> pd.DataFrame:
    """Query the chat API for every golden question and attach the results.

    Args:
        df: Golden dataset with a "question" column.

    Returns:
        df with two new columns: "answer" and "contexts" (list[str] per row).
    """
    rag_ckpt = {}
    if os.path.exists(RAG_CHECKPOINT_FILE):
        with open(RAG_CHECKPOINT_FILE, "r") as f:
            rag_ckpt = json.load(f)
        logger.info(f"Resumed RAG checkpoint: {len(rag_ckpt)} questions already collected")

    results: list = [None] * len(df)
    todo: list[tuple[int, str]] = []
    for i, question in enumerate(df["question"], start=1):
        q_key = str(i)
        cached = rag_ckpt.get(q_key)
        # Reuse a cached answer only if it was produced for this exact question.
        # Index keys alone can't detect a reordered or regenerated dataset.
        if cached is not None and cached.get("question") == question:
            logger.info(f"[{i}/{len(df)}] Skipping (cached): {question!r}")
            results[i - 1] = {"answer": cached["answer"], "contexts": cached["contexts"]}
            continue
        if cached is not None:
            logger.warning(f"[{i}/{len(df)}] Cache mismatch, re-querying: {question!r}")
        todo.append((i, question))

    def _safe_query(question: str) -> tuple[dict[str, Any], bool]:
        logger.info(f"Querying chat API: {question!r}")
        try:
            result = with_retry(
                lambda: _chat_once(question),
                f"chat {question[:50]!r}",
                max_attempts=CHAT_MAX_ATTEMPTS,
                waits=CHAT_RETRY_WAITS,
            )
        except EvalAborted:
            raise
        except Exception as e:
            record_failure("chat", question, e)
            return {"answer": "", "contexts": []}, False
        record_success()
        return result, True

    # ex.map yields in input order, so checkpoint writes stay sequential and the
    # resume prefix stays valid even when queries complete out of order.
    ex = ThreadPoolExecutor(max_workers=EVAL_MAX_WORKERS)
    try:
        for (i, question), (result, ok) in zip(todo, ex.map(_safe_query, [q for _, q in todo])):
            results[i - 1] = result
            # Failed calls are not checkpointed, so a resume re-queries them
            # instead of freezing an empty answer into the run.
            if not ok:
                continue
            rag_ckpt[str(i)] = {"question": question, **result}
            with open(RAG_CHECKPOINT_FILE, "w") as f:
                json.dump(rag_ckpt, f)
    finally:
        # On abort, drop queued queries instead of waiting for all of them.
        ex.shutdown(wait=True, cancel_futures=True)

    df = df.copy()
    df["answer"] = [r["answer"] for r in results]
    df["contexts"] = [r["contexts"] for r in results]
    return df


def run_ragas(df: pd.DataFrame) -> pd.DataFrame:
    """Score the collected rows with RAGAS's LLM-judged RAG metrics.

    Uses JUDGE_MODEL on OpenRouter as the judge LLM, and a local sentence
    embedding model for the reference-free answer_relevancy metric.

    Args:
        df: Rows with question, answer, contexts, ground_truth.

    Returns:
        DataFrame with one column per RAGAS metric, indexed like df.
    """
    from datasets import Dataset
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=JUDGE_MODEL,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            temperature=0,
            extra_body=provider_body(JUDGE_PROVIDER),
        )
    )
    judge_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )

    dataset = [
        {
            "user_input": row.question,
            "response": row.answer,
            "retrieved_contexts": row.contexts,
            "reference": row.ground_truth,
        }
        for row in df.itertuples()
    ]

    checkpoint = load_checkpoint()
    all_results = checkpoint["results"]

    # Keep only the leading cached rows that still match the current dataset
    # (same question and same answer). Anything after the first mismatch is
    # discarded and re-scored, so a changed dataset or regenerated answers
    # can't leak stale scores into the run.
    valid = 0
    while (
        valid < len(all_results)
        and valid < len(dataset)
        and all_results[valid].get("user_input") == dataset[valid]["user_input"]
        and all_results[valid].get("response") == dataset[valid]["response"]
    ):
        valid += 1
    if valid < len(all_results):
        logger.warning(f"Discarding {len(all_results) - valid} stale RAGAS checkpoint rows")
    all_results = all_results[:valid]
    start_idx = valid

    from ragas import RunConfig
    run_config = RunConfig(
        max_workers=1, timeout=600, max_retries=RAGAS_MAX_RETRIES, max_wait=RAGAS_MAX_WAIT
    )

    # scored holds every row scored in this run, by index. The checkpoint grows
    # only while no row has failed permanently. After a gap, later rows are kept
    # in memory but not checkpointed, so the checkpoint stays a clean prefix and
    # a resume re-scores from the gap.
    scored: dict[int, dict] = dict(enumerate(all_results))
    gap = False
    for idx, row in enumerate(dataset):
        if idx < start_idx:
            continue

        if not row["response"] or not row["retrieved_contexts"]:
            # Collect failed (empty answer, no contexts): not judged, so no fake 0.
            # A NaN marker keeps the checkpoint prefix aligned with the dataset.
            logger.warning(f"Row {idx + 1} skipped: collect failed, not judged")
            marker = {m: float("nan") for m in METRIC_COLS}
            marker.update(user_input=row["user_input"], response=row["response"], skipped=True)
            scored[idx] = marker
            if not gap:
                all_results.append(marker)
                save_checkpoint(all_results, idx)
            continue

        def _score_once(row=row) -> dict:
            result = evaluate(
                Dataset.from_dict({k: [v] for k, v in row.items()}),
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=judge_llm,
                embeddings=judge_embeddings,
                # Surface judge/parse failures as exceptions instead of silent NaN rows.
                raise_exceptions=True,
                run_config=run_config,
            )
            record = result.to_pandas().to_dict(orient="records")[0]
            if has_nan(record, METRIC_COLS):
                raise ValueError("NaN in RAGAS metrics")
            return record

        try:
            record = with_retry(_score_once, f"ragas row {idx + 1}")
        except EvalAborted:
            raise
        except Exception as e:
            record_failure("ragas", idx + 1, e)
            gap = True
            continue
        record_success()
        # Store the inputs next to the scores so the next run can verify them.
        record["user_input"] = row["user_input"]
        record["response"] = row["response"]
        scored[idx] = record
        if gap:
            logger.warning(f"Row {idx + 1} scored but not checkpointed (an earlier row failed)")
            continue
        all_results.append(record)
        save_checkpoint(all_results, idx)
        print(f"Saved checkpoint at idx {idx}")

    if gap:
        logger.warning(f"Checkpoint stopped at the first failed row; {len(all_results)} rows saved")

    nan_row = {m: float("nan") for m in METRIC_COLS}
    final_df = pd.DataFrame([scored.get(i, nan_row) for i in range(len(dataset))])
    print(final_df.mean(numeric_only=True))

    # Checkpoint is not deleted automatically.
    # Delete evaluation/checkpoint.json manually to start over.

    return final_df[METRIC_COLS]


def run_deepeval_hallucination(df: pd.DataFrame) -> pd.Series:
    """Score each row's answer for hallucination against its retrieved contexts.

    Uses DeepEval's HallucinationMetric, judged by JUDGE_MODEL on OpenRouter
    through a DeepEvalBaseLLM adapter.

    Args:
        df: Rows with question, answer, contexts.

    Returns:
        Series named "hallucination_grounded", indexed like df. Higher is better:
        the fraction of the answer's claims that the retrieved contexts support
        (deepeval 4.x scores YES = factual alignment, and passes when score >=
        threshold). 1 = fully grounded, 0 = no claim supported. None = not scored.
    """
    from deepeval.metrics import HallucinationMetric
    from deepeval.models import DeepEvalBaseLLM
    from deepeval.test_case import LLMTestCase

    class OpenRouterJudge(DeepEvalBaseLLM):
        """Minimal DeepEvalBaseLLM adapter around an OpenRouter chat model."""

        def __init__(self, model: str):
            self.client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
            self.model = model

        def load_model(self):
            return self.client

        def generate(self, prompt: str) -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                extra_body=provider_body(JUDGE_PROVIDER),
            )
            return response.choices[0].message.content or ""

        async def a_generate(self, prompt: str) -> str:
            return self.generate(prompt)

        def get_model_name(self) -> str:
            return self.model

    judge = OpenRouterJudge(JUDGE_MODEL)

    # Per-row checkpoint keyed by row index. An entry is reused only while its
    # question and answer still match the dataset row, so a changed dataset is
    # re-scored. Only valid numeric scores are stored; failures are retried on resume.
    ds_ckpt: dict[str, dict] = {}
    if os.path.exists(DEEPEVAL_CHECKPOINT_FILE):
        with open(DEEPEVAL_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for i, row in enumerate(df.itertuples(), start=1):
            entry = saved.get(str(i))
            if entry and entry.get("question") == row.question and entry.get("answer") == row.answer and _valid_score(entry.get("score")):
                ds_ckpt[str(i)] = entry
    cached = {int(k): v["score"] for k, v in ds_ckpt.items()}
    if cached:
        logger.info(f"Resumed DeepEval checkpoint: {len(cached)} rows already scored")
    ds_lock = threading.Lock()

    def _save_deepeval(i: int, row: Any, score: float) -> None:
        with ds_lock:
            ds_ckpt[str(i)] = {"question": row.question, "answer": row.answer, "score": score}
            tmp = DEEPEVAL_CHECKPOINT_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(ds_ckpt, f, ensure_ascii=False)
            os.replace(tmp, DEEPEVAL_CHECKPOINT_FILE)

    def _score_row(args: tuple[int, Any]) -> tuple[float | None, str]:
        i, row = args
        if i in cached:
            return cached[i], "cached"
        if not row.answer or not row.contexts:
            logger.warning(f"[{i}/{len(df)}] Collect failed (no answer/contexts); skipping hallucination check")
            return None, "skipped"
        test_case = LLMTestCase(input=row.question, actual_output=row.answer, context=row.contexts)

        def _measure() -> float:
            # A fresh metric per call: HallucinationMetric keeps verdicts and score
            # on the instance, so sharing one across worker threads would race.
            metric = HallucinationMetric(model=judge, threshold=0.5)
            metric.measure(test_case)
            if metric.score is None or math.isnan(metric.score):
                raise ValueError("DeepEval returned no score")
            return metric.score

        try:
            score = with_retry(_measure, f"deepeval row {i}")
        except EvalAborted:
            raise
        except Exception as e:
            record_failure("deepeval", i, e)
            return None, "failed"
        record_success()
        _save_deepeval(i, row, score)
        return score, "scored"

    # DeepEval fails per row, not per run, so a failed row is recorded as None
    # and the run continues. ex.map keeps results in row order, so the Series
    # lines up with df. Totals are logged at the end so failures stay visible.
    ex = ThreadPoolExecutor(max_workers=EVAL_MAX_WORKERS)
    try:
        outcomes = list(ex.map(_score_row, enumerate(df.itertuples(), start=1)))
    finally:
        ex.shutdown(wait=True, cancel_futures=True)

    scores = [score for score, _ in outcomes]
    statuses = [status for _, status in outcomes]
    failed = statuses.count("failed")
    skipped = statuses.count("skipped")
    reused = statuses.count("cached")
    logger.warning(
        f"DeepEval summary: {failed} failed, {skipped} skipped (no contexts), "
        f"{reused} reused from checkpoint, {len(df) - failed - skipped - reused} scored, out of {len(df)} rows"
    )
    return pd.Series(scores, index=df.index, name="hallucination_grounded")


def print_summary(df: pd.DataFrame) -> None:
    """Print mean scores for every evaluation metric column.

    Args:
        df: Merged results DataFrame.
    """
    metric_cols = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "hallucination_grounded"]
    print("\n=== Evaluation summary (mean scores, higher = better for all metrics) ===")
    print(f"generator_model      {RAG_GENERATOR_MODEL}  (provider: {RAG_GENERATOR_PROVIDER or 'unpinned'})")
    print(f"judge_model          {JUDGE_MODEL}  (provider: {JUDGE_PROVIDER or 'unpinned'})")
    # Collect-failed rows have an empty answer and were never judged; they are excluded from the means.
    collect_failed = int((df["answer"] == "").sum()) if "answer" in df.columns else 0
    print(f"rows judged: {len(df) - collect_failed}/{len(df)}  "
          f"(skipped, collect failed: {collect_failed}; means use only judged rows)")
    for col in metric_cols:
        if col in df.columns:
            print(f"{col:24s} {df[col].mean():.3f}   missing: {df[col].isna().sum()}/{len(df)}")

    # Rows with any missing metric, so partial failures are visible in the aggregate.
    present = [c for c in metric_cols if c in df.columns]
    incomplete = int(df[present].isna().any(axis=1).sum())
    print(f"rows with at least one missing metric: {incomplete}/{len(df)}")


def main() -> None:
    try:
        _run_evaluation()
    finally:
        # Written even on abort, so the failures behind an abort are kept on disk.
        write_failed_rows()


def _run_evaluation() -> None:
    df = load_golden_dataset()
    if df.empty:
        logger.warning(f"{DATASET_PATH} is empty; nothing to evaluate")
        return

    for role, provider in (
        ("RAG generator", RAG_GENERATOR_PROVIDER),
        ("judge", JUDGE_PROVIDER),
    ):
        if not provider:
            logger.warning(f"{role} provider is not pinned; set it in .env for a reproducible run")

    df = collect_rag_outputs(df)

    logger.info("Running RAGAS metrics...")
    ragas_scores = run_ragas(df)

    logger.info("Running DeepEval HallucinationMetric...")
    hallucination_scores = run_deepeval_hallucination(df)

    results = pd.concat([df.reset_index(drop=True), ragas_scores.reset_index(drop=True)], axis=1)
    results["hallucination_grounded"] = hallucination_scores.reset_index(drop=True)
    # Record which models produced these numbers so runs stay comparable.
    results["generator_model"] = RAG_GENERATOR_MODEL
    results["generator_provider"] = RAG_GENERATOR_PROVIDER or "unpinned"
    results["judge_model"] = JUDGE_MODEL
    results["judge_provider"] = JUDGE_PROVIDER or "unpinned"

    results.to_csv(RESULTS_PATH, index=False)
    logger.info(f"Wrote {len(results)} scored rows to {RESULTS_PATH}")

    print_summary(results)


if __name__ == "__main__":
    main()
