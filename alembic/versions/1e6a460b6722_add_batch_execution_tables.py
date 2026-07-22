"""Add durable Gemini batch execution tables.

Revision ID: 1e6a460b6722
Revises: d4e5f6a7b8c9
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1e6a460b6722"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_job_name", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_step", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("provider = 'google_ai'", name="ck_batch_jobs_provider"),
        sa.CheckConstraint(
            "state IN ('submitting', 'pending', 'running', 'succeeded', "
            "'failed', 'cancelled', 'expired')",
            name="ck_batch_jobs_state",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_batch_jobs_open",
        "batch_jobs",
        ["state"],
        postgresql_where=sa.text("state IN ('submitting', 'pending', 'running')"),
        sqlite_where=sa.text("state IN ('submitting', 'pending', 'running')"),
    )
    op.create_index(
        "uq_batch_jobs_provider_job_name",
        "batch_jobs",
        ["provider_job_name"],
        unique=True,
        postgresql_where=sa.text("provider_job_name IS NOT NULL"),
        sqlite_where=sa.text("provider_job_name IS NOT NULL"),
    )

    op.create_table(
        "batch_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("batch_job_id", sa.String(length=36), nullable=True),
        sa.Column("model_step", sa.String(length=40), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=True),
        sa.Column("request_payload", _JSON, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("fallback_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'submitted', 'succeeded', 'fallback', 'failed')",
            name="ck_batch_requests_status",
        ),
        sa.CheckConstraint(
            "fallback_attempts >= 0", name="ck_batch_requests_fallback_attempts"
        ),
        sa.ForeignKeyConstraint(
            ["batch_job_id"], ["batch_jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_key", name="uq_batch_requests_key"),
    )
    op.create_index("ix_batch_requests_job", "batch_requests", ["batch_job_id"])
    op.create_index(
        "ix_batch_requests_pending",
        "batch_requests",
        ["model_step", "model_id", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "uq_batch_requests_active_target",
        "batch_requests",
        ["model_step", "content_id"],
        unique=True,
        postgresql_where=sa.text(
            "content_id IS NOT NULL AND status IN "
            "('pending', 'claimed', 'submitted', 'fallback')"
        ),
        sqlite_where=sa.text(
            "content_id IS NOT NULL AND status IN "
            "('pending', 'claimed', 'submitted', 'fallback')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_batch_requests_active_target", table_name="batch_requests")
    op.drop_index("ix_batch_requests_pending", table_name="batch_requests")
    op.drop_index("ix_batch_requests_job", table_name="batch_requests")
    op.drop_table("batch_requests")
    op.drop_index("uq_batch_jobs_provider_job_name", table_name="batch_jobs")
    op.drop_index("ix_batch_jobs_open", table_name="batch_jobs")
    op.drop_table("batch_jobs")
