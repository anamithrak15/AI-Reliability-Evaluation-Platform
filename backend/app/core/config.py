from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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
    # Per user; the global cap stops many users from queueing unbounded work on a small host.
    max_active_runs: int = 3
    max_active_runs_global: int = 10
    max_datasets_per_user: int = 20
    max_retries: int = 2
    retry_backoff_seconds: float = 0.25
    max_run_seconds: int = 300
    stale_run_seconds: int = 900
    # Run evaluations in the API process instead of a separate RQ worker (single-service hosting).
    run_worker_inline: bool = False
    inline_worker_threads: int = 2
    # Number of reverse proxies in front of the API that append to X-Forwarded-For (0 = none).
    trusted_proxy_hops: int = 0
    # Accounts. SECRET_KEY signs session cookies; set a long random value outside development.
    environment: str = "development"
    secret_key: str = "dev-only-insecure-secret-change-me-0123456789"
    cookie_secure: bool = False
    session_days: int = 7
    allow_registration: bool = True
    password_min_length: int = 10
    # Auth attempts use the shared rate-limit window; 0 disables a bucket.
    auth_register_per_window: int = 5
    auth_login_ip_per_window: int = 10
    auth_login_email_per_window: int = 5
    # Verification / reset emails per address and per account.
    auth_email_per_window: int = 5
    # Email. Without smtp_host nothing is sent (the message is logged outside production).
    require_email_verification: bool = False
    # Frontend origin used to build links in emails, e.g. https://app.example.com
    public_base_url: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    # HTTPS delivery through Brevo; preferred over SMTP because free hosts often block SMTP ports.
    # The sender (SMTP_FROM) must be a verified sender in the Brevo account.
    brevo_api_key: str = ""
    verify_token_minutes: int = 1440
    reset_token_minutes: int = 30
    demo_dataset_path: str = str(
        Path(__file__).resolve().parents[3] / "datasets" / "demo_dataset.json"
    )

    @field_validator("database_url")
    @classmethod
    def _driver(cls, url: str) -> str:
        # Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver name.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


_DEFAULT_SECRET = Settings.model_fields["secret_key"].default


def assert_safe_for_environment(s: Settings) -> None:
    """Refuse to start in production with development defaults."""
    if s.environment.lower() != "production":
        return
    problems = []
    if s.secret_key == _DEFAULT_SECRET or len(s.secret_key) < 32:
        problems.append("SECRET_KEY must be a random value of at least 32 characters")
    if not s.cookie_secure:
        problems.append("COOKIE_SECURE must be true")
    if s.require_email_verification and not (
        (s.brevo_api_key or s.smtp_host) and s.smtp_from
    ):
        problems.append("REQUIRE_EMAIL_VERIFICATION needs BREVO_API_KEY or SMTP_HOST, and SMTP_FROM")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
