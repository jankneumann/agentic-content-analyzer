"""drop_newsletter_table_and_fk

Drop the legacy Newsletter model and its references.

This migration:
1. Drops the newsletter_id FK column from newsletter_summaries
2. Drops the newsletters table entirely

IMPORTANT: This migration is IRREVERSIBLE in production without data backup.
All Newsletter data will be lost. Ensure all data has been migrated to Content
model before running this migration.

Revision ID: 8753a5a83a94
Revises: c9d0e1f2a3b4
Create Date: 2026-01-23 23:33:32.519427

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8753a5a83a94"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop Newsletter table and newsletter_id FK from summaries."""
    # Step 1: Drop the foreign key constraint from newsletter_summaries
    # The constraint name follows the naming convention: fk_<table>_<column>_<referenced_table>
    op.drop_constraint(
        "newsletter_summaries_newsletter_id_fkey",
        "newsletter_summaries",
        type_="foreignkey",
    )

    # Step 2: Drop the index on newsletter_id
    op.drop_index(
        "ix_newsletter_summaries_newsletter_id",
        table_name="newsletter_summaries",
    )

    # Step 3: Drop the newsletter_id column from newsletter_summaries
    op.drop_column("newsletter_summaries", "newsletter_id")

    # Step 4: Drop the newsletters table
    op.drop_table("newsletters")


def downgrade() -> None:
    """Recreate Newsletter table and newsletter_id FK.

    WARNING: This does not restore any data - only the schema.
    """
    # Step 1: Recreate the newsletters table
    op.create_table(
        "newsletters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=500), nullable=False),
        sa.Column("sender", sa.String(length=500), nullable=True),
        sa.Column("publication", sa.String(length=500), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("received_date", sa.DateTime(), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("links_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Step 2: Add the newsletter_id column back to newsletter_summaries
    op.add_column(
        "newsletter_summaries",
        sa.Column("newsletter_id", sa.Integer(), nullable=True),
    )

    # Step 3: Add the index
    op.create_index(
        "ix_newsletter_summaries_newsletter_id",
        "newsletter_summaries",
        ["newsletter_id"],
    )

    # Step 4: Add the foreign key constraint
    op.create_foreign_key(
        "newsletter_summaries_newsletter_id_fkey",
        "newsletter_summaries",
        "newsletters",
        ["newsletter_id"],
        ["id"],
    )
