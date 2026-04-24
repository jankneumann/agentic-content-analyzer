"""Add readwise content source and highlights table.

Revision ID: c9d3e1f5a7b2
Revises: 1455833d558b
Create Date: 2026-04-24

Adds:
1. 'readwise' to the contentsource Postgres enum
2. highlights table for user annotations on contents, summaries, and digests
   - content_id always roots to a Content (required)
   - (target_kind, target_id) identifies the anchored text stream
   - Soft-delete via deleted_at (Readwise tombstones land here)
   - Unique partial index on readwise_id for idempotent Readwise sync

Note: ALTER TYPE ... ADD VALUE is safe in a transaction on PostgreSQL 12+
as long as the new value is not used in the same transaction. The migration
only adds the enum value and creates the highlights table; the 'readwise'
value is first inserted at runtime by the ingestion service.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "c9d3e1f5a7b2"
down_revision: Union[str, None] = "1455833d558b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add 'readwise' to the contentsource enum
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'readwise'")

    # 2. Create highlights table
    op.create_table(
        "highlights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "content_id",
            sa.Integer(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_kind", sa.String(20), nullable=False, server_default="content"),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("location", sa.Integer(), nullable=True),
        sa.Column("location_type", sa.String(20), nullable=True),
        sa.Column(
            "tags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source", sa.String(20), nullable=False, server_default="native"),
        sa.Column("readwise_id", sa.String(64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("highlighted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "target_kind IN ('content','summary','digest')",
            name="chk_highlight_target_kind",
        ),
        sa.CheckConstraint(
            "target_kind <> 'content' OR target_id = content_id",
            name="chk_highlight_content_target_matches_root",
        ),
    )

    # 3. Indexes
    op.execute(
        "CREATE INDEX ix_highlights_content_active "
        "ON highlights (content_id) WHERE deleted_at IS NULL"
    )
    op.create_index(
        "ix_highlights_target",
        "highlights",
        ["target_kind", "target_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_highlights_readwise_id "
        "ON highlights (readwise_id) WHERE readwise_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_highlights_readwise_id")
    op.drop_index("ix_highlights_target", table_name="highlights")
    op.execute("DROP INDEX IF EXISTS ix_highlights_content_active")
    op.drop_table("highlights")
    # PostgreSQL does not support removing values from enums; 'readwise' remains.
