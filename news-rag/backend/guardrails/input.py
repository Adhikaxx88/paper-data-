"""Input guardrails run on every search query before it reaches Qdrant/OpenRouter.

Checks run in a fixed order and stop at the first failure:
encoding -> regex -> injection -> multi-turn -> scope (LLM classifier).
The LLM-backed checks (scope, language) call GUARDRAIL_MODEL on OpenRouter and
fail open on any transport or parse error, so a provider outage never blocks search.
"""
import base64
import binascii
import json
import re
import unicodedata
from dataclasses import dataclass

import httpx
from loguru import logger

from config import (
    GUARDRAIL_MODEL,
    GUARDRAIL_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    TOPIC_QUERIES,
    TOPIC_QUERIES_ID,
    provider_body,
)

if not OPENROUTER_API_KEY:
    logger.warning(
        "OPENROUTER_API_KEY is empty: scope_check and language_detect will fail open on every query"
    )


def _build_scope_topics() -> str:
    """Extract every unique sub-area name from TOPIC_QUERIES/TOPIC_QUERIES_ID.

    Used to make scope_check's classifier prompt aware of the pipeline's
    actual (niche) topic coverage, so it doesn't reject valid but specific
    queries just because they weren't in a hand-written topic list.

    Returns:
        Comma-separated, sorted, deduplicated sub-area names, e.g.
        "Conditions, Gen Z & City, ...".
    """
    topics = set()
    for lang_queries in (TOPIC_QUERIES, TOPIC_QUERIES_ID):
        for sub_areas in lang_queries.values():
            topics.update(sub_areas.keys())
    return ", ".join(sorted(topics))


SCOPE_TOPICS = _build_scope_topics()

_SCOPE_SYSTEM_PROMPT = (
    "You are a content classifier for a research pipeline on Indonesian youth and child mental health. "
    f"The pipeline tracks these specific topic areas: {SCOPE_TOPICS}.\n\n"
    "Relevant queries include anything about: mental health conditions (depression, anxiety, OCD, eating "
    "disorders, schizophrenia, panic attacks), suicide and self-harm, bullying (school/cyber), academic "
    "stress, social media effects, substance use, digital wellbeing, family dynamics (including TKI/migrant "
    "worker families, orphan teens, domestic violence, divorce, economic hardship), trauma and resilience, "
    "post-pandemic mental health, disaster survivors, pesantren/Islamic boarding school students, "
    "vocational/SMK students, Gen Z mental health, city-specific data (Jakarta, Surabaya, Bandung, "
    "Yogyakarta, Medan), mental health interventions (mindfulness, art therapy, peer counseling), and "
    "statistics/surveys on the above.\n\n"
    "Reject ONLY queries completely unrelated to Indonesian youth mental health: e.g. cooking recipes, "
    "sports scores, stock prices, celebrity gossip, general technology unrelated to youth wellbeing.\n\n"
    'Respond ONLY with JSON: {"relevant": true/false, "reason": "string"}'
)

_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

_INJECTION_KEYWORDS = (
    "ignore previous",
    "ignore all instructions",
    "system prompt",
    "you are now",
    "jailbreak",
    "act as",
)

_REGEX_PATTERNS = [
    re.compile(r"ignore (previous|above|all instructions?)", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"forget (everything|instructions)", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"act as (a|an)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DROP TABLE", re.IGNORECASE),
    re.compile(r"SELECT \* FROM", re.IGNORECASE),
    re.compile(r"';\s*--"),
]

_INJECTION_PHRASES = ("new task:", "disregard", "actually your", "your real instructions")
_ROLE_KEYWORDS = ("admin", "developer", "god mode")


@dataclass
class GuardrailResult:
    """Outcome of a single guardrail check.

    Attributes:
        passed: Whether the check passed.
        check_name: Short identifier for the check (e.g. "regex").
        reason: Human-readable explanation, empty when passed.
    """

    passed: bool
    check_name: str
    reason: str = ""


def encoding_check(text: str) -> tuple[str, GuardrailResult]:
    """Normalize unicode and reject text hiding an instruction inside base64.

    Args:
        text: Raw user-supplied text.

    Returns:
        (normalized_text, result) — normalized_text is NFKC-normalized text,
        returned even when the check fails.
    """
    normalized = unicodedata.normalize("NFKC", text)

    for match in _BASE64_RE.findall(normalized):
        try:
            decoded = base64.b64decode(match, validate=True).decode("utf-8", errors="ignore")
        except (binascii.Error, ValueError):
            continue
        if any(keyword in decoded.lower() for keyword in _INJECTION_KEYWORDS):
            return normalized, GuardrailResult(
                passed=False, check_name="encoding", reason="Base64-encoded injection attempt detected"
            )

    return normalized, GuardrailResult(passed=True, check_name="encoding")


def regex_check(text: str) -> GuardrailResult:
    """Reject text matching any known prompt-injection / SQLi regex pattern.

    Args:
        text: Text to check (normalized).

    Returns:
        GuardrailResult; fails on the first matching pattern.
    """
    for pattern in _REGEX_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(
                passed=False, check_name="regex", reason=f"Matched forbidden pattern: {pattern.pattern}"
            )
    return GuardrailResult(passed=True, check_name="regex")


def injection_check(text: str) -> GuardrailResult:
    """Reject text combining role-hijack phrasing with a privileged role keyword.

    Args:
        text: Text to check (normalized).

    Returns:
        GuardrailResult; fails if an injection phrase and a role keyword both appear.
    """
    lowered = text.lower()

    for phrase in _INJECTION_PHRASES:
        if phrase in lowered:
            return GuardrailResult(
                passed=False, check_name="injection", reason=f"Detected injection phrase: '{phrase}'"
            )

    if "pretend" in lowered and any(role in lowered for role in _ROLE_KEYWORDS):
        return GuardrailResult(
            passed=False, check_name="injection", reason="Detected role-hijack attempt combined with 'pretend'"
        )

    return GuardrailResult(passed=True, check_name="injection")


def multiturn_check(text: str, history: list[str]) -> GuardrailResult:
    """Re-run regex/injection checks over the last 5 history turns plus the current text.

    Catches attacks that escalate gradually across a conversation instead of
    tripping single-turn checks.

    Args:
        text: Current query text (normalized).
        history: Prior queries in the session, oldest first.

    Returns:
        GuardrailResult; fails if the combined window trips regex_check or injection_check.
    """
    window = "\n".join(history[-5:] + [text])

    regex_result = regex_check(window)
    if not regex_result.passed:
        return GuardrailResult(
            passed=False, check_name="multiturn", reason=f"Escalating pattern across turns: {regex_result.reason}"
        )

    injection_result = injection_check(window)
    if not injection_result.passed:
        return GuardrailResult(
            passed=False,
            check_name="multiturn",
            reason=f"Escalating injection across turns: {injection_result.reason}",
        )

    return GuardrailResult(passed=True, check_name="multiturn")


def _openrouter_post(messages: list[dict[str, str]], json_mode: bool, timeout: float) -> httpx.Response:
    """POST a chat completion to OpenRouter using GUARDRAIL_MODEL.

    Only transport and HTTP-status errors are raised here (as httpx exceptions).
    Response parsing is left to the caller so its own fail-open branch catches it.

    Args:
        messages: OpenAI-style chat messages.
        json_mode: Ask the provider for a JSON object response.
        timeout: Request timeout in seconds.

    Returns:
        The successful httpx.Response.
    """
    body: dict = {"model": GUARDRAIL_MODEL, "messages": messages, **provider_body(GUARDRAIL_PROVIDER)}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    response = httpx.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def _message_text(response: httpx.Response) -> str:
    """Extract the assistant text from an OpenRouter chat completion response.

    Raises:
        KeyError / IndexError / ValueError if the body is not the expected shape.
    """
    return response.json()["choices"][0]["message"]["content"] or ""


def scope_check(text: str) -> GuardrailResult:
    """Ask the guardrail LLM whether the query is in-scope for this research system.

    Fails open (passes) if OpenRouter is unreachable, returns an HTTP error, or
    the response can't be parsed, so a provider outage never blocks search.
    Every fail-open path logs a WARNING.

    Args:
        text: Current query text (normalized).

    Returns:
        GuardrailResult based on the LLM's relevance classification.
    """
    messages = [
        {"role": "system", "content": _SCOPE_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    try:
        response = _openrouter_post(messages, json_mode=True, timeout=15.0)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning(f"OpenRouter unreachable for scope_check, failing open: {e}")
        return GuardrailResult(passed=True, check_name="scope", reason="OpenRouter unreachable, failed open")
    except httpx.HTTPError as e:
        logger.warning(f"OpenRouter scope_check request failed (check API key/quota), failing open: {e}")
        return GuardrailResult(passed=True, check_name="scope", reason="OpenRouter request failed, failed open")

    try:
        payload = json.loads(_message_text(response))
        relevant = bool(payload.get("relevant", True))
        reason = str(payload.get("reason", ""))
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Could not parse scope_check LLM response, failing open: {e}")
        return GuardrailResult(passed=True, check_name="scope", reason="Unparseable LLM response, failed open")

    if not relevant:
        return GuardrailResult(passed=False, check_name="scope", reason=reason or "Query out of scope")

    return GuardrailResult(passed=True, check_name="scope")


def language_detect(text: str) -> tuple[GuardrailResult, str]:
    """Ask the guardrail LLM to detect whether the query is Indonesian or English.

    Always passes (informational check) — falls back to "auto" whenever
    OpenRouter is unreachable, its response is unparseable, or confidence is low.
    Every fail-open path logs a WARNING.

    Args:
        text: Current query text (normalized).

    Returns:
        (GuardrailResult, detected_lang) — detected_lang is "id", "en", or "auto".
    """
    prompt = (
        "Detect the language of this text. Is it Indonesian (id) or English (en)?\n"
        'Respond ONLY with JSON, no explanation: {"language": "id", "confidence": 0.95}\n'
        f'Text: "{text[:300]}"'
    )

    detected = "auto"
    try:
        response = _openrouter_post([{"role": "user", "content": prompt}], json_mode=False, timeout=15.0)
        raw = _message_text(response) or "{}"
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        data = json.loads(match.group()) if match else {}
        lang = data.get("language", "auto")
        confidence = float(data.get("confidence", 0.0))
        detected = lang if (confidence >= 0.75 and lang in ("id", "en")) else "auto"
    except Exception as e:
        logger.warning(f"language_detect failed via OpenRouter, failing open to auto: {e}")
        detected = "auto"

    return GuardrailResult(passed=True, check_name="language_detect", reason=f"detected={detected}"), detected


def run_input_guardrails(text: str, history: list[str]) -> tuple[str, list[GuardrailResult], str]:
    """Run all input guardrail checks in order, stopping at the first failure.

    Args:
        text: Raw user query.
        history: Prior queries in the session, oldest first.

    Returns:
        (normalized_text, results, detected_lang) — results holds every check
        that ran, including the failing one if any (checks after a failure do
        not run). detected_lang is "id"/"en"/"auto"; it is only computed when
        every other check passes, and defaults to "auto" otherwise.
    """
    normalized_text, encoding_result = encoding_check(text)
    results = [encoding_result]
    if not encoding_result.passed:
        return normalized_text, results, "auto"

    regex_result = regex_check(normalized_text)
    results.append(regex_result)
    if not regex_result.passed:
        return normalized_text, results, "auto"

    injection_result = injection_check(normalized_text)
    results.append(injection_result)
    if not injection_result.passed:
        return normalized_text, results, "auto"

    multiturn_result = multiturn_check(normalized_text, history)
    results.append(multiturn_result)
    if not multiturn_result.passed:
        return normalized_text, results, "auto"

    scope_result = scope_check(normalized_text)
    results.append(scope_result)
    if not scope_result.passed:
        return normalized_text, results, "auto"

    lang_result, detected_lang = language_detect(normalized_text)
    results.append(lang_result)
    return normalized_text, results, detected_lang
