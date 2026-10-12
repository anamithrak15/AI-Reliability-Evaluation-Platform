from dataclasses import dataclass

from app.core.config import get_settings
from app.evaluation.mock_adapter import MOCK_MODELS


@dataclass(frozen=True)
class ModelInfo:
    alias: str
    provider: str
    description: str


_MOCK_DESCRIPTIONS = {
    "fast-model": "Simulated low-latency model (demo)",
    "accurate-model": "Simulated higher-accuracy, slower model (demo)",
    "flaky-model": "Simulated model with timeouts and provider errors (demo)",
}

EVALUATION_PROFILES = {
    "classification-v1": "Label classification scored per case from its evaluation_config",
    "generic-v1": "Generic scoring from each case's evaluation_config",
}


def _live_aliases() -> dict[str, str]:
    settings = get_settings()
    return settings.live_models if settings.enable_live_llm else {}


def list_models() -> list[ModelInfo]:
    models = [
        ModelInfo(alias, "mock", _MOCK_DESCRIPTIONS.get(alias, "Simulated model"))
        for alias in MOCK_MODELS
    ]
    models += [
        ModelInfo(alias, target.split("/", 1)[0], f"Live model via LiteLLM ({target})")
        for alias, target in _live_aliases().items()
        if alias not in MOCK_MODELS
    ]
    return models


def is_allowed_model(alias: str) -> bool:
    return alias in MOCK_MODELS or alias in _live_aliases()
