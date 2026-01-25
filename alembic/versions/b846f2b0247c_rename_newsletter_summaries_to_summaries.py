"""rename_newsletter_summaries_to_summaries

Renames the newsletter_summaries table to summaries as part of
the Newsletter model deprecation. Also updates all related
indexes and foreign key constraints.

Revision ID: b846f2b0247c
Revises: 8753a5a83a94
Create Date: 2026-01-23 23:49:40.805483

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b846f2b0247c"
down_revision: Union[str, None] = "8753a5a83a94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename newsletter_summaries to summaries."""
    conn = op.get_bind()

    # Check if source table exists
    result = conn.execute(
        sa.text(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'newsletter_summaries'
            """
        )
    )
    if not result.fetchone():
        # Table already renamed or doesn't exist
        return

    # Step 1: Drop the old foreign key constraint on content_id (if exists)
    conn.execute(
        sa.text(
            """
            ALTER TABLE newsletter_summaries
            DROP CONSTRAINT IF EXISTS fk_newsletter_summaries_content_id
            """
        )
    )

    # Step 2: Drop the images table's FK to newsletter_summaries (if exists)
    conn.execute(
        sa.text(
            """
            ALTER TABLE images
            DROP CONSTRAINT IF EXISTS images_summary_id_fkey
            """
        )
    )

    # Step 3: Drop indexes before renaming (will recreate with new names)
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_newsletter_summaries_content_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_newsletter_summaries_content_id_unique"))

    # Step 4: Rename the table
    op.rename_table("newsletter_summaries", "summaries")

    # Step 5: Recreate the content_id index with new name
    op.create_index(
        "ix_summaries_content_id",
        "summaries",
        ["content_id"],
    )

    # Step 6: Recreate the foreign key constraint with new name
    op.create_foreign_key(
        "fk_summaries_content_id",
        "summaries",
        "contents",
        ["content_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Step 7: Recreate images table's FK to summaries (only if column exists)
    result = conn.execute(
        sa.text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'images' AND column_name = 'summary_id'
            """
        )
    )
    if result.fetchone():
        op.create_foreign_key(
            "images_summary_id_fkey",
            "images",
            "summaries",
            ["summary_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Revert summaries back to newsletter_summaries."""
    conn = op.get_bind()

    # Check if summaries table exists
    result = conn.execute(
        sa.text(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'summaries'
            """
        )
    )
    if not result.fetchone():
        # Table doesn't exist or already renamed back
        return

    # Step 1: Drop the new foreign key constraint
    conn.execute(
        sa.text(
            """
            ALTER TABLE summaries
            DROP CONSTRAINT IF EXISTS fk_summaries_content_id
            """
        )
    )

    # Step 2: Drop images FK
    conn.execute(
        sa.text(
            """
            ALTER TABLE images
            DROP CONSTRAINT IF EXISTS images_summary_id_fkey
            """
        )
    )

    # Step 3: Drop the new index
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_summaries_content_id"))

    # Step 4: Rename table back
    op.rename_table("summaries", "newsletter_summaries")

    # Step 5: Recreate the old index
    op.create_index(
        "ix_newsletter_summaries_content_id",
        "newsletter_summaries",
        ["content_id"],
    )

    # Step 6: Recreate the old foreign key constraint
    op.create_foreign_key(
        "fk_newsletter_summaries_content_id",
        "newsletter_summaries",
        "contents",
        ["content_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Step 7: Recreate images FK (only if column exists)
    result = conn.execute(
        sa.text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'images' AND column_name = 'summary_id'
            """
        )
    )
    if result.fetchone():
        op.create_foreign_key(
            "images_summary_id_fkey",
            "images",
            "newsletter_summaries",
            ["summary_id"],
            ["id"],
            ondelete="SET NULL",
        )
