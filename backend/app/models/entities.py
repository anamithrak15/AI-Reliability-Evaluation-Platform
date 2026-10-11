import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = _ts()

    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number"),)

    id: Mapped[uuid.UUID] = _pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts()

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="dataset_version")


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # not a pytest class
    __table_args__ = (UniqueConstraint("dataset_version_id", "case_key"),)

    id: Mapped[uuid.UUID] = _pk()
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=False
    )
    case_key: Mapped[str] = mapped_column(String(200), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evaluation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _ts()

    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="test_cases")


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[uuid.UUID] = _pk()
    alias: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    litellm_model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Non-secret settings only; credentials come from env/secret manager.
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("ix_evaluation_runs_status_created_at", "status", "created_at"),
        Index("ix_evaluation_runs_dataset_version_created_at", "dataset_version_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evaluation_runs.id"))
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()
    requested_by: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(Text)


class CaseResult(Base):
    __tablename__ = "case_results"
    __table_args__ = (
        UniqueConstraint("run_id", "test_case_id", "model_alias"),
        Index("ix_case_results_run_model", "run_id", "model_alias"),
        Index("ix_case_results_case_model", "test_case_id", "model_alias"),
    )

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    output: Mapped[Any | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message_redacted: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = _ts()


class CaseMetric(Base):
    __tablename__ = "case_metrics"
    __table_args__ = (UniqueConstraint("case_result_id", "metric_name"),)

    id: Mapped[uuid.UUID] = _pk()
    case_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_results.id"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    metric_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class RunSummary(Base):
    __tablename__ = "run_summaries"
    # One row per (run, model); the spec's run-level unique would allow only one model.
    __table_args__ = (UniqueConstraint("run_id", "model_alias"),)

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    success_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    failure_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    latency_p50_ms: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    latency_p95_ms: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    total_output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class RegressionFinding(Base):
    __tablename__ = "regression_findings"
    __table_args__ = (Index("ix_regression_findings_run_severity", "run_id", "severity"),)

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    delta: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _ts()
