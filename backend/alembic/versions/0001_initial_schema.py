"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", pg.UUID(as_uuid=True), primary_key=True)


def _created():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "datasets",
        _id(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_id", sa.String(100)),
        _created(),
    )
    op.create_table(
        "dataset_versions",
        _id(),
        sa.Column("dataset_id", pg.UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        _created(),
        sa.UniqueConstraint("dataset_id", "version_number"),
    )
    op.create_table(
        "test_cases",
        _id(),
        sa.Column(
            "dataset_version_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("case_key", sa.String(200), nullable=False),
        sa.Column("input", pg.JSONB(), nullable=False),
        sa.Column("expected_output", pg.JSONB()),
        sa.Column("evaluation_config", pg.JSONB(), nullable=False),
        sa.Column("tags", pg.JSONB(), nullable=False),
        _created(),
        sa.UniqueConstraint("dataset_version_id", "case_key"),
    )
    op.create_table(
        "model_configs",
        _id(),
        sa.Column("alias", sa.String(100), nullable=False, unique=True),
        sa.Column("litellm_model", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config_json", pg.JSONB(), nullable=False),
    )
    op.create_table(
        "evaluation_runs",
        _id(),
        sa.Column(
            "dataset_version_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("baseline_run_id", pg.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id")),
        sa.Column("config_snapshot", pg.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        _created(),
        sa.Column("requested_by", sa.String(100)),
        sa.Column("error_summary", sa.Text()),
    )
    op.create_index(
        "ix_evaluation_runs_status_created_at", "evaluation_runs", ["status", "created_at"]
    )
    op.create_index(
        "ix_evaluation_runs_dataset_version_created_at",
        "evaluation_runs",
        ["dataset_version_id", "created_at"],
    )
    op.create_table(
        "case_results",
        _id(),
        sa.Column("run_id", pg.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("test_case_id", pg.UUID(as_uuid=True), sa.ForeignKey("test_cases.id"), nullable=False),
        sa.Column("model_alias", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("output", pg.JSONB()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message_redacted", sa.Text()),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        _created(),
        sa.UniqueConstraint("run_id", "test_case_id", "model_alias"),
    )
    op.create_index("ix_case_results_run_model", "case_results", ["run_id", "model_alias"])
    op.create_index("ix_case_results_case_model", "case_results", ["test_case_id", "model_alias"])
    op.create_table(
        "case_metrics",
        _id(),
        sa.Column(
            "case_result_id", pg.UUID(as_uuid=True), sa.ForeignKey("case_results.id"), nullable=False
        ),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6)),
        sa.Column("metric_details", pg.JSONB()),
        sa.UniqueConstraint("case_result_id", "metric_name"),
    )
    op.create_index("ix_case_metrics_metric_name", "case_metrics", ["metric_name"])
    op.create_table(
        "run_summaries",
        _id(),
        sa.Column("run_id", pg.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("model_alias", sa.String(100), nullable=False),
        sa.Column("quality_score", sa.Numeric(8, 6)),
        sa.Column("success_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("failure_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("latency_p50_ms", sa.Numeric(12, 2)),
        sa.Column("latency_p95_ms", sa.Numeric(12, 2)),
        sa.Column("total_input_tokens", sa.BigInteger()),
        sa.Column("total_output_tokens", sa.BigInteger()),
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8)),
        sa.Column("summary_json", pg.JSONB(), nullable=False),
        sa.UniqueConstraint("run_id", "model_alias"),
    )
    op.create_table(
        "regression_findings",
        _id(),
        sa.Column("run_id", pg.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("model_alias", sa.String(100), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("baseline_value", sa.Numeric(18, 6)),
        sa.Column("current_value", sa.Numeric(18, 6)),
        sa.Column("delta", sa.Numeric(18, 6)),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        _created(),
    )
    op.create_index(
        "ix_regression_findings_run_severity", "regression_findings", ["run_id", "severity"]
    )


def downgrade() -> None:
    for table in (
        "regression_findings",
        "run_summaries",
        "case_metrics",
        "case_results",
        "evaluation_runs",
        "model_configs",
        "test_cases",
        "dataset_versions",
        "datasets",
    ):
        op.drop_table(table)
