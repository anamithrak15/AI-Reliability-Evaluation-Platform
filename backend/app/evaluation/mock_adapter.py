"""Deterministic mock LLM adapter used in demo mode and tests (no network, no cost)."""

import hashlib
import json
from dataclasses import dataclass

MOCK_MODELS: dict[str, dict[str, float]] = {
    # error_every: every Nth case (by stable hash) is misclassified.
    "fast-model": {"latency_ms": 50, "error_every": 4},
    "accurate-model": {"latency_ms": 150, "error_every": 12},
}

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


def generate(model_alias: str, case_key: str, prompt: str) -> MockResponse:
    if model_alias not in MOCK_MODELS:
        raise ValueError(f"unknown mock model: {model_alias}")
    cfg = MOCK_MODELS[model_alias]

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
