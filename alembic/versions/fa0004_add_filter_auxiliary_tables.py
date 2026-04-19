"""Add persona_filter_profiles and filter_feedback_events tables.

Revision ID: fa0004filter03
Revises: fa0003filter02
Create Date: 2026-04-19 09:15:00.000000

- persona_filter_profiles: cache of persona interest embeddings keyed by
  (persona_id, embedding_provider, embedding_model). Invalidated by
  interest_hash change.
- filter_feedback_events: append-only log of reviewer decisions paired with
  the original filter score. v1 is fire-and-forget; future changes may train
  calibration from this log.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "fa0004filter03"
down_revision: Union[str, None] = "fa0003filter02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The embedding column is declared as JSONB to avoid a hard pgvector
    # dependency in environments where the extension is not installed.
    # Existing DocumentChunk.embedding uses a raw-SQL path for pgvector too.
    op.create_table(
        "persona_filter_profiles",
        sa.Column("persona_id", sa.String(length=200), primary_key=True),
        sa.Column("embedding_provider", sa.String(length=100), primary_key=True),
        sa.Column("embedding_model", sa.String(length=200), primary_key=True),
        sa.Column("interest_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", JSONB, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "filter_feedback_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "content_id",
            sa.Integer(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("persona_id", sa.String(length=200), nullable=False),
        sa.Column("original_score", sa.Float(), nullable=False),
        sa.Column("original_decision", sa.String(length=20), nullable=False),
        sa.Column("original_tier", sa.String(length=20), nullable=True),
        sa.Column("reviewer_decision", sa.String(length=20), nullable=False),
        sa.Column("reviewer_id", sa.String(length=200), nullable=True),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("metadata_json", JSONB, nullable=True),
    )
    op.create_index(
        "ix_filter_feedback_events_content",
        "filter_feedback_events",
        ["content_id"],
        unique=False,
    )
    op.create_index(
        "ix_filter_feedback_events_persona_reviewed",
        "filter_feedback_events",
        ["persona_id", sa.text("reviewed_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_filter_feedback_events_persona_reviewed", table_name="filter_feedback_events")
    op.drop_index("ix_filter_feedback_events_content", table_name="filter_feedback_events")
    op.drop_table("filter_feedback_events")
    op.drop_table("persona_filter_profiles")
