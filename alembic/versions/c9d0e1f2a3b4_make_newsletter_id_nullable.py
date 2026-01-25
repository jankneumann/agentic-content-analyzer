"""Make newsletter_id nullable on newsletter_summaries

As part of the Newsletter deprecation (D2), this migration allows summaries
to be created without a newsletter_id, using content_id as the primary FK.

Changes:
- Drop unique constraint on newsletter_id
- Make newsletter_id nullable
- Fix any existing summaries with newsletter_id=0 (hack marker)

Revision ID: c9d0e1f2a3b4
Revises: a8b9c0d1e2f3
Create Date: 2026-01-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Fix any existing hack rows (newsletter_id=0)
    # These should have content_id set - set newsletter_id to NULL
    op.execute("""
        UPDATE newsletter_summaries
        SET newsletter_id = NULL
        WHERE newsletter_id = 0
    """)

    # Step 2: Drop the unique constraint on newsletter_id
    # Note: The constraint name may vary - use introspection or known name
    op.drop_constraint(
        'newsletter_summaries_newsletter_id_key',
        'newsletter_summaries',
        type_='unique'
    )

    # Step 3: Make newsletter_id nullable
    op.alter_column(
        'newsletter_summaries',
        'newsletter_id',
        existing_type=sa.INTEGER(),
        nullable=True
    )

    # Step 4: Add a partial unique index on content_id (where not null)
    # This ensures one summary per content
    op.execute("""
        CREATE UNIQUE INDEX ix_newsletter_summaries_content_id_unique
        ON newsletter_summaries (content_id)
        WHERE content_id IS NOT NULL
    """)


def downgrade() -> None:
    # Step 1: Drop the partial unique index on content_id
    op.execute("DROP INDEX IF EXISTS ix_newsletter_summaries_content_id_unique")

    # Step 2: Make newsletter_id not nullable (will fail if NULLs exist)
    op.alter_column(
        'newsletter_summaries',
        'newsletter_id',
        existing_type=sa.INTEGER(),
        nullable=False
    )

    # Step 3: Re-add unique constraint on newsletter_id
    op.create_unique_constraint(
        'newsletter_summaries_newsletter_id_key',
        'newsletter_summaries',
        ['newsletter_id']
    )
