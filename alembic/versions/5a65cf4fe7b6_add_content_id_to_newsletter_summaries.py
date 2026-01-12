"""Add content_id to newsletter_summaries

Adds a content_id column to link summaries directly to the unified Content model.
This completes the migration from Newsletter to Content by providing direct FK access.

Revision ID: 5a65cf4fe7b6
Revises: 41d180035213
Create Date: 2026-01-12 15:21:35.565407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a65cf4fe7b6'
down_revision: Union[str, None] = '41d180035213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add content_id column (nullable for now)
    op.add_column(
        'newsletter_summaries',
        sa.Column('content_id', sa.Integer(), nullable=True)
    )

    # Create index for efficient lookups
    op.create_index(
        'ix_newsletter_summaries_content_id',
        'newsletter_summaries',
        ['content_id'],
        unique=False
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_newsletter_summaries_content_id',
        'newsletter_summaries',
        'contents',
        ['content_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Populate content_id by joining through source_id
    # newsletter_summaries.newsletter_id -> newsletters.id -> newsletters.source_id -> contents.source_id -> contents.id
    op.execute("""
        UPDATE newsletter_summaries ns
        SET content_id = c.id
        FROM newsletters n
        JOIN contents c ON n.source_id = c.source_id
        WHERE ns.newsletter_id = n.id
    """)


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint(
        'fk_newsletter_summaries_content_id',
        'newsletter_summaries',
        type_='foreignkey'
    )

    # Remove index
    op.drop_index(
        'ix_newsletter_summaries_content_id',
        table_name='newsletter_summaries'
    )

    # Remove column
    op.drop_column('newsletter_summaries', 'content_id')
