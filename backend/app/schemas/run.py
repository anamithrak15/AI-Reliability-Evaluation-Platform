from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: UUID
    model_aliases: list[str] = Field(min_length=1)
    baseline_run_id: UUID | None = None
    evaluation_profile: str = "classification-v1"
    max_concurrency: int = Field(default=3, ge=1)
    max_cases: int = Field(default=100, ge=1)

    @field_validator("model_aliases")
    @classmethod
    def _aliases(cls, aliases: list[str]) -> list[str]:
        limit = get_settings().max_models_per_run
        if len(aliases) > limit:
            raise ValueError(f"at most {limit} models per run")
        if len(set(aliases)) != len(aliases):
            raise ValueError("model_aliases must be unique")
        return aliases


class Progress(BaseModel):
    total_pairs: int
    completed_pairs: int
    by_status: dict[str, int]


class RunOut(BaseModel):
    id: UUID
    dataset_version_id: UUID
    status: str
    baseline_run_id: UUID | None
    config: dict[str, Any]
    progress: Progress
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None


class CaseResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    test_case_id: UUID
    case_key: str
    model_alias: str
    status: str
    output: Any | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    error_code: str | None
    error_message_redacted: str | None
    attempt_count: int
    created_at: datetime


class ModelOut(BaseModel):
    alias: str
    provider: str
    description: str


class ProfileOut(BaseModel):
    name: str
    description: str
