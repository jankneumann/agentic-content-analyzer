"""add_markdown_content_and_theme_tags_columns

Revision ID: 41d180035213
Revises: b84e1839d132
Create Date: 2026-01-11 19:39:22.311775

Adds markdown_content and theme_tags columns to newsletter_summaries and digests
tables to support the unified content model's markdown-first architecture.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "41d180035213"
down_revision: Union[str, None] = "b84e1839d132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to newsletter_summaries table
    op.add_column(
        "newsletter_summaries",
        sa.Column(
            "markdown_content",
            sa.Text(),
            nullable=True,
            comment="Full markdown representation of the summary",
        ),
    )
    op.add_column(
        "newsletter_summaries",
        sa.Column(
            "theme_tags",
            sa.JSON(),
            nullable=True,
            comment="Extracted theme tags as JSON array",
        ),
    )

    # Add columns to digests table
    op.add_column(
        "digests",
        sa.Column(
            "markdown_content",
            sa.Text(),
            nullable=True,
            comment="Full markdown representation of the digest",
        ),
    )
    op.add_column(
        "digests",
        sa.Column(
            "theme_tags",
            sa.JSON(),
            nullable=True,
            comment="Extracted theme tags as JSON array",
        ),
    )
    op.add_column(
        "digests",
        sa.Column(
            "source_content_ids",
            sa.JSON(),
            nullable=True,
            comment="List of content IDs used in this digest",
        ),
    )


def downgrade() -> None:
    # Remove columns from digests table
    op.drop_column("digests", "source_content_ids")
    op.drop_column("digests", "theme_tags")
    op.drop_column("digests", "markdown_content")

    # Remove columns from newsletter_summaries table
    op.drop_column("newsletter_summaries", "theme_tags")
    op.drop_column("newsletter_summaries", "markdown_content")
