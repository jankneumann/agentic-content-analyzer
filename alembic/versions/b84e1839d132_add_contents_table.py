"""add_contents_table

Revision ID: b84e1839d132
Revises: 4d78f715c284
Create Date: 2026-01-11 18:44:05.413413

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b84e1839d132"
down_revision: Union[str, None] = "4d78f715c284"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum types for use in both upgrade and downgrade
content_source_values = [
    "gmail",
    "rss",
    "file_upload",
    "youtube",
    "manual",
    "webpage",
    "other",
]
content_status_values = [
    "pending",
    "parsing",
    "parsed",
    "processing",
    "completed",
    "failed",
]


def upgrade() -> None:
    """Create contents table for unified content model."""
    # Create PostgreSQL enum types using raw SQL to avoid double-creation
    op.execute("CREATE TYPE contentsource AS ENUM ('gmail', 'rss', 'file_upload', 'youtube', 'manual', 'webpage', 'other')")
    op.execute("CREATE TYPE contentstatus AS ENUM ('pending', 'parsing', 'parsed', 'processing', 'completed', 'failed')")

    # Create contents table using PostgreSQL ENUM type reference
    op.create_table(
        "contents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Source identification
        sa.Column(
            "source_type",
            postgresql.ENUM(*content_source_values, name="contentsource", create_type=False),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        # Identity / Metadata
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("author", sa.String(length=500), nullable=True),
        sa.Column("publication", sa.String(length=500), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        # Canonical content - MARKDOWN FIRST
        sa.Column("markdown_content", sa.Text(), nullable=False),
        # Structured extractions
        sa.Column("tables_json", sa.JSON(), nullable=True),
        sa.Column("links_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        # Raw preservation
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("raw_format", sa.String(length=50), nullable=True),
        # Parsing metadata
        sa.Column("parser_used", sa.String(length=100), nullable=True),
        sa.Column("parser_version", sa.String(length=50), nullable=True),
        # Deduplication
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_id", sa.Integer(), nullable=True),
        # Processing status
        sa.Column(
            "status",
            postgresql.ENUM(*content_status_values, name="contentstatus", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "ingested_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["canonical_id"],
            ["contents.id"],
            name="fk_contents_canonical_id",
            ondelete="SET NULL",
        ),
    )

    # Create indexes
    op.create_index("ix_contents_source_type", "contents", ["source_type"])
    op.create_index("ix_contents_publication", "contents", ["publication"])
    op.create_index("ix_contents_published_date", "contents", ["published_date"])
    op.create_index("ix_contents_content_hash", "contents", ["content_hash"])
    op.create_index("ix_contents_status", "contents", ["status"])

    # Composite unique index on source_type + source_id
    op.create_index(
        "idx_contents_source", "contents", ["source_type", "source_id"], unique=True
    )

    # Composite index for querying by publication and date
    op.create_index(
        "idx_contents_publication_date", "contents", ["publication", "published_date"]
    )


def downgrade() -> None:
    """Drop contents table and enums."""
    # Drop indexes
    op.drop_index("idx_contents_publication_date", table_name="contents")
    op.drop_index("idx_contents_source", table_name="contents")
    op.drop_index("ix_contents_status", table_name="contents")
    op.drop_index("ix_contents_content_hash", table_name="contents")
    op.drop_index("ix_contents_published_date", table_name="contents")
    op.drop_index("ix_contents_publication", table_name="contents")
    op.drop_index("ix_contents_source_type", table_name="contents")

    # Drop table
    op.drop_table("contents")

    # Drop enums using raw SQL
    op.execute("DROP TYPE IF EXISTS contentstatus")
    op.execute("DROP TYPE IF EXISTS contentsource")
