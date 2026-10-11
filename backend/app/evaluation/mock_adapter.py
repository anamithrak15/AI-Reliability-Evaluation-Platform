"""Deterministic mock LLM adapter used in demo mode and tests (no network, no cost)."""

import hashlib
import json
from dataclasses import dataclass

from app.evaluation.errors import LLMProviderError, LLMTimeout

MOCK_MODELS: dict[str, dict[str, float]] = {
    # error_every: every Nth case (by stable hash) is misclassified.
    "fast-model": {"latency_ms": 50, "error_every": 4},
    "accurate-model": {"latency_ms": 150, "error_every": 12},
    "flaky-model": {"latency_ms": 100, "error_every": 6},
}

FLAKY_MODELS = {"flaky-model"}
TIMEOUT_LATENCY_MS = 30_000

_KEYWORDS = {
    "billing": ("charged", "invoice", "refund", "payment", "subscription"),
    "account_access": ("password", "login", "log in", "locked", "2fa"),
    "technical": ("error", "crash", "bug", "not loading", "timeout"),
}
_CATEGORIES = list(_KEYWORDS)


@dataclass(frozen=True)
class MockResponse:
    content: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


def _classify(text: str) -> str:
    lowered = text.lower()
    for category, words in _KEYWORDS.items():
        if any(w in lowered for w in words):
            return category
    return "technical"


def _stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:8], 16)


def scenario_for(model_alias: str, case_key: str) -> str:
    """ok | permanent_error | timeout | transient_then_ok, stable per (model, case)."""
    if model_alias not in FLAKY_MODELS:
        return "ok"
    bucket = _stable_int(f"scenario:{model_alias}:{case_key}") % 8
    return {0: "permanent_error", 1: "timeout", 2: "transient_then_ok", 3: "transient_then_ok"}.get(
        bucket, "ok"
    )


def generate(model_alias: str, case_key: str, prompt: str, attempt: int = 1) -> MockResponse:
    if model_alias not in MOCK_MODELS:
        raise ValueError(f"unknown mock model: {model_alias}")
    cfg = MOCK_MODELS[model_alias]

    scenario = scenario_for(model_alias, case_key)
    if scenario == "permanent_error":
        raise LLMProviderError(
            "mock provider rejected the request",
            code="mock_provider_error",
            transient=False,
            latency_ms=20,
        )
    if scenario == "timeout":
        raise LLMTimeout(latency_ms=TIMEOUT_LATENCY_MS)
    if scenario == "transient_then_ok" and attempt == 1:
        raise LLMProviderError(
            "mock provider rate limited", code="rate_limited", transient=True, latency_ms=10
        )

    category = _classify(prompt)
    if _stable_int(f"{model_alias}:{case_key}") % int(cfg["error_every"]) == 0:
        category = _CATEGORIES[(_CATEGORIES.index(category) + 1) % len(_CATEGORIES)]

    content = json.dumps({"category": category, "priority": "medium"})
    return MockResponse(
        content=content,
        latency_ms=int(cfg["latency_ms"]),
        input_tokens=max(1, len(prompt.split())),
        output_tokens=max(1, len(content.split())),
    )
