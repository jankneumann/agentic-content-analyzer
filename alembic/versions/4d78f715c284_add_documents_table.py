"""add_documents_table

Revision ID: 4d78f715c284
Revises: d8c7c9b9430a
Create Date: 2026-01-10 23:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d78f715c284"
down_revision: Union[str, None] = "d8c7c9b9430a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents table for parsed document storage."""
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # Source information
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("source_format", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),  # SHA-256
        # Parser information
        sa.Column("parser_used", sa.String(50), nullable=False),
        # Content storage (markdown-centric)
        sa.Column("markdown_content", sa.Text(), nullable=False),
        # Optional structured data (JSON)
        sa.Column("tables_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("links_json", sa.JSON(), nullable=True),
        # Relationship to newsletter
        sa.Column(
            "newsletter_id",
            sa.Integer(),
            sa.ForeignKey("newsletters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Processing status
        sa.Column("status", sa.String(50), nullable=False, default="pending"),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        # Timestamps
        sa.Column(
            "uploaded_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index("idx_documents_file_hash", "documents", ["file_hash"])
    op.create_index("idx_documents_status", "documents", ["status"])
    op.create_index("idx_documents_parser", "documents", ["parser_used"])
    op.create_index("idx_documents_newsletter", "documents", ["newsletter_id"])
    op.create_index("idx_documents_source_format", "documents", ["source_format"])


def downgrade() -> None:
    """Drop documents table."""
    op.drop_index("idx_documents_source_format", table_name="documents")
    op.drop_index("idx_documents_newsletter", table_name="documents")
    op.drop_index("idx_documents_parser", table_name="documents")
    op.drop_index("idx_documents_status", table_name="documents")
    op.drop_index("idx_documents_file_hash", table_name="documents")
    op.drop_table("documents")
