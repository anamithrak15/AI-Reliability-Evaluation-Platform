"""add email verification timestamp to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""
import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    # Accounts that exist before verification was introduced are grandfathered in.
    op.execute("UPDATE users SET email_verified_at = created_at")


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
