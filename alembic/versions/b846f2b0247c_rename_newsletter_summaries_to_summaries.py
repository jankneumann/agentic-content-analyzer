"""rename_newsletter_summaries_to_summaries

Renames the newsletter_summaries table to summaries as part of
the Newsletter model deprecation. Also updates all related
indexes and foreign key constraints.

Revision ID: b846f2b0247c
Revises: 8753a5a83a94
Create Date: 2026-01-23 23:49:40.805483

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b846f2b0247c"
down_revision: Union[str, None] = "8753a5a83a94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename newsletter_summaries to summaries."""
    # Step 1: Drop the old foreign key constraint on content_id
    op.drop_constraint(
        "fk_newsletter_summaries_content_id",
        "newsletter_summaries",
        type_="foreignkey",
    )

    # Step 2: Drop the images table's FK to newsletter_summaries (if exists)
    # The images table has a summary_id column that references newsletter_summaries
    try:
        op.drop_constraint(
            "images_summary_id_fkey",
            "images",
            type_="foreignkey",
        )
    except Exception:
        # Constraint may not exist or have different name
        pass

    # Step 3: Drop indexes before renaming (will recreate with new names)
    op.drop_index(
        "ix_newsletter_summaries_content_id",
        table_name="newsletter_summaries",
    )

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

    # Step 7: Recreate images table's FK to summaries
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
    # Step 1: Drop the new foreign key constraint
    op.drop_constraint(
        "fk_summaries_content_id",
        "summaries",
        type_="foreignkey",
    )

    # Step 2: Drop images FK
    try:
        op.drop_constraint(
            "images_summary_id_fkey",
            "images",
            type_="foreignkey",
        )
    except Exception:
        pass

    # Step 3: Drop the new index
    op.drop_index(
        "ix_summaries_content_id",
        table_name="summaries",
    )

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

    # Step 7: Recreate images FK
    op.create_foreign_key(
        "images_summary_id_fkey",
        "images",
        "newsletter_summaries",
        ["summary_id"],
        ["id"],
        ondelete="SET NULL",
    )
