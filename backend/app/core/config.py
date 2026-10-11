from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://aireliability:change-me@localhost:5432/aireliability"
    redis_url: str = "redis://localhost:6379/0"
    demo_mode: bool = True
    enable_live_llm: bool = False
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    max_cases_per_dataset: int = 100
    max_request_bytes: int = 1_048_576
    demo_dataset_path: str = str(
        Path(__file__).resolve().parents[3] / "datasets" / "demo_dataset.json"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
