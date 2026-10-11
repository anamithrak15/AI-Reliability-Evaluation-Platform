from dataclasses import dataclass

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

# Live models join this list on Day 4 behind ENABLE_LIVE_LLM.
EVALUATION_PROFILES = {
    "classification-v1": "Label classification scored per case from its evaluation_config",
    "generic-v1": "Generic scoring from each case's evaluation_config",
}


def list_models() -> list[ModelInfo]:
    return [
        ModelInfo(alias, "mock", _MOCK_DESCRIPTIONS.get(alias, "Simulated model"))
        for alias in MOCK_MODELS
    ]


def is_allowed_model(alias: str) -> bool:
    return alias in MOCK_MODELS
