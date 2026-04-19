"""Add filter_* columns and indexes to contents.

Revision ID: fa0003filter02
Revises: fa0002filter01
Create Date: 2026-04-19 09:10:00.000000

Adds the columns and indexes required by IngestionFilterService to record
per-item filter decisions. Safe to run in a single transaction.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "fa0003filter02"
down_revision: Union[str, None] = "fa0002filter01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("filter_score", sa.Float(), nullable=True))
    op.add_column("contents", sa.Column("filter_decision", sa.String(length=20), nullable=True))
    op.add_column("contents", sa.Column("filter_tier", sa.String(length=20), nullable=True))
    op.add_column("contents", sa.Column("filter_reason", sa.Text(), nullable=True))
    op.add_column("contents", sa.Column("priority_bucket", sa.String(length=20), nullable=True))
    op.add_column(
        "contents",
        sa.Column("filtered_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_contents_status_filter_score",
        "contents",
        ["status", sa.text("filter_score DESC")],
        unique=False,
    )
    op.create_index(
        "ix_contents_filter_decision_ingested",
        "contents",
        ["filter_decision", sa.text("ingested_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_contents_filter_decision_ingested", table_name="contents")
    op.drop_index("ix_contents_status_filter_score", table_name="contents")
    op.drop_column("contents", "filtered_at")
    op.drop_column("contents", "priority_bucket")
    op.drop_column("contents", "filter_reason")
    op.drop_column("contents", "filter_tier")
    op.drop_column("contents", "filter_decision")
    op.drop_column("contents", "filter_score")
