import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.security import redact
from app.evaluation import mock_adapter
from app.evaluation.errors import LLMProviderError, LLMTimeout
from app.evaluation.mock_adapter import MOCK_MODELS


@dataclass(frozen=True)
class LLMResult:
    content: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None  # None means unknown, never zero


def _litellm() -> Any:
    # Use the bundled price map; the default import-time fetch from GitHub fails offline.
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    return litellm


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


_QUOTA_MARKERS = ("insufficient_quota", "no credits", "exceeded your current quota", "billing")


def _provider_message(exc: Exception) -> str:
    return redact(f"{type(exc).__name__}: {exc}", max_len=300)


def _is_quota_error(exc: Exception) -> bool:
    # Providers report exhausted credit as a rate limit, but retrying cannot help.
    text = str(exc).lower()
    return any(marker in text for marker in _QUOTA_MARKERS)


def live_call(litellm_model: str, messages: list[dict[str, Any]]) -> LLMResult:
    """One LiteLLM call. Credentials come from server env vars (e.g. OPENAI_API_KEY)."""
    settings = get_settings()
    litellm = _litellm()
    transient = (
        litellm.RateLimitError, litellm.ServiceUnavailableError,
        litellm.InternalServerError, litellm.APIConnectionError,
    )
    start = time.monotonic()

    def elapsed() -> int:
        return int((time.monotonic() - start) * 1000)

    try:
        resp = litellm.completion(
            model=litellm_model, messages=messages, temperature=0,
            timeout=settings.live_timeout_seconds,
            max_tokens=settings.live_max_output_tokens,
            num_retries=0,  # retries are owned by the orchestrator
        )
    except litellm.Timeout:
        raise LLMTimeout(latency_ms=elapsed()) from None
    except transient as exc:
        if _is_quota_error(exc):
            raise LLMProviderError(
                _provider_message(exc), code="quota_exceeded", transient=False, latency_ms=elapsed()
            ) from None
        raise LLMProviderError(
            _provider_message(exc), code="provider_transient", transient=True, latency_ms=elapsed()
        ) from None
    except Exception as exc:
        raise LLMProviderError(
            _provider_message(exc), code="provider_error", transient=False, latency_ms=elapsed()
        ) from None

    usage = getattr(resp, "usage", None)
    try:
        cost = litellm.completion_cost(completion_response=resp)
    except Exception:
        cost = None  # no pricing for this model: unknown, not zero
    return LLMResult(
        content=resp.choices[0].message.content or "",
        latency_ms=elapsed(),
        input_tokens=_int_or_none(getattr(usage, "prompt_tokens", None)),
        output_tokens=_int_or_none(getattr(usage, "completion_tokens", None)),
        estimated_cost_usd=Decimal(str(cost)) if cost is not None else None,
    )


def call_model(
    model_alias: str, case_key: str, messages: list[dict[str, Any]], attempt: int
) -> LLMResult:
    """Single call; raises LLMError subclasses."""
    if model_alias in MOCK_MODELS:
        prompt = "\n".join(str(m.get("content", "")) for m in messages)
        r = mock_adapter.generate(model_alias, case_key, prompt, attempt=attempt)
        return LLMResult(r.content, r.latency_ms, r.input_tokens, r.output_tokens, None)
    settings = get_settings()
    if settings.enable_live_llm and model_alias in settings.live_models:
        return live_call(settings.live_models[model_alias], messages)
    raise ValueError(f"model '{model_alias}' is not available")
