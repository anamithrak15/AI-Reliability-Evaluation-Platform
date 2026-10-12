from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.run import RunOut


class ModelSummaryOut(BaseModel):
    model_alias: str
    scheduled: int
    executed: int
    successes: int
    failures: int
    skipped: int
    success_rate: float
    failure_rate: float
    quality_score: float | None
    quality_n: int
    accuracy: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_n: int
    total_input_tokens: int | None
    total_output_tokens: int | None
    token_n: int
    estimated_cost_usd: float | None
    cost_n: int
    cost_per_case_usd: float | None
    cost_complete: bool


class RankedModelOut(BaseModel):
    model_alias: str
    eligible: bool
    reasons: list[str]
    components: dict[str, float]
    missing_components: list[str]
    overall_score: float | None
    rank: int | None


class RankingOut(BaseModel):
    models: list[RankedModelOut]
    recommended: str | None
    explanation: str
    notes: list[str]
    constraints: dict[str, float]
    weights: dict[str, float]


class ComparisonOut(BaseModel):
    run_id: UUID
    status: str
    dataset_name: str | None
    dataset_version_number: int | None
    content_hash: str | None
    evaluation_profile: str | None
    models: list[ModelSummaryOut]
    ranking: RankingOut


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_alias: str
    metric_name: str
    baseline_value: float | None
    current_value: float | None
    delta: float | None
    severity: str
    explanation: str


class RegressionsOut(BaseModel):
    run_id: UUID
    baseline_run_id: UUID | None
    # no_baseline | incompatible | evaluated
    state: str
    incompatibilities: list[str]
    thresholds: dict[str, float]
    findings: list[FindingOut]
    highest_severity: str | None


class BaselineSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_run_id: UUID | None


class ReportOut(BaseModel):
    generated_at: datetime
    run: RunOut
    comparison: ComparisonOut
    regressions: RegressionsOut
    note: str
