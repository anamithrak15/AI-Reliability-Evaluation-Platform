from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.evaluation import mock_adapter
from app.evaluation.mock_adapter import MOCK_MODELS


@dataclass(frozen=True)
class LLMResult:
    content: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None  # None means unknown, never zero


def call_model(
    model_alias: str, case_key: str, messages: list[dict[str, Any]], attempt: int
) -> LLMResult:
    """Single call; raises LLMError subclasses. Live LiteLLM routing arrives on Day 4."""
    if model_alias not in MOCK_MODELS:
        raise ValueError(f"model '{model_alias}' is not available")
    prompt = "\n".join(str(m.get("content", "")) for m in messages)
    r = mock_adapter.generate(model_alias, case_key, prompt, attempt=attempt)
    return LLMResult(r.content, r.latency_ms, r.input_tokens, r.output_tokens, None)
