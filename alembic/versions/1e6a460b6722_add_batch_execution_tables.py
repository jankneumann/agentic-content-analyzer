"""Add batch_jobs and batch_requests tables (Gemini batch execution)

Revision ID: 1e6a460b6722
Revises: b8f8b5ededed
Create Date: 2026-06-10 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e6a460b6722"
down_revision: Union[str, None] = "b8f8b5ededed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batch_jobs_open", "batch_jobs", ["state"])

    op.create_table(
        "batch_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("batch_job_id", sa.String(length=36), nullable=True),
        sa.Column("model_step", sa.String(length=40), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("target_table", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_job_id"], ["batch_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_key", name="uq_batch_requests_key"),
    )
    op.create_index("ix_batch_requests_job", "batch_requests", ["batch_job_id"])
    op.create_index(
        "ix_batch_requests_pending",
        "batch_requests",
        ["model_step", "model_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_batch_requests_pending", table_name="batch_requests")
    op.drop_index("ix_batch_requests_job", table_name="batch_requests")
    op.drop_table("batch_requests")
    op.drop_index("ix_batch_jobs_open", table_name="batch_jobs")
    op.drop_table("batch_jobs")
