from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://aireliability:change-me@localhost:5432/aireliability"
    redis_url: str = "redis://localhost:6379/0"
    demo_mode: bool = True
    enable_live_llm: bool = False
    # alias -> LiteLLM model string, e.g. {"gpt-mini": "openai/gpt-4o-mini"}; credentials stay in env.
    live_models: dict[str, str] = {}
    live_timeout_seconds: float = 30.0
    live_max_output_tokens: int = 512
    # Per-run USD cap for each model; 0 disables. Only priced calls count toward it.
    live_budget_usd_per_model: float = 0.05
    live_budget_overrides: dict[str, float] = {}
    # Regression thresholds: drops/rises are absolute fractions (0.03 = 3 points); p95/cost rises are relative.
    regression_quality_drop: float = 0.03
    regression_failure_rise: float = 0.02
    regression_p95_rise_pct: float = 0.25
    regression_cost_rise_pct: float = 0.20
    regression_quality_floor: float = 0.5
    regression_min_samples: int = 5
    # Ranking constraints; 0 disables the optional ones.
    rank_min_quality: float = 0.5
    rank_max_failure_rate: float = 0.2
    rank_max_p95_ms: float = 0
    rank_max_cost_per_case_usd: float = 0
    rank_min_samples: int = 5
    rank_weight_quality: float = 0.60
    rank_weight_latency: float = 0.25
    rank_weight_cost: float = 0.15
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    # Per client address; 0 disables a bucket. Run creation is the costly call, so it is limited harder.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_per_window: int = 240
    rate_limit_run_creates_per_window: int = 10
    max_cases_per_dataset: int = 100
    max_request_bytes: int = 1_048_576
    max_models_per_run: int = 3
    max_concurrency_limit: int = 5
    max_active_runs: int = 3
    max_retries: int = 2
    retry_backoff_seconds: float = 0.25
    max_run_seconds: int = 300
    stale_run_seconds: int = 900
    demo_dataset_path: str = str(
        Path(__file__).resolve().parents[3] / "datasets" / "demo_dataset.json"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
