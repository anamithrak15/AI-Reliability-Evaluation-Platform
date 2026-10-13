"""add idempotency key to evaluation runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""
import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_runs", sa.Column("idempotency_key", sa.String(100)))
    op.create_unique_constraint(
        "uq_evaluation_runs_idempotency_key", "evaluation_runs", ["idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_evaluation_runs_idempotency_key", "evaluation_runs", type_="unique")
    op.drop_column("evaluation_runs", "idempotency_key")
