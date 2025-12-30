"""add content hash for deduplication

Revision ID: 16b8f13de9b6
Revises: a950af83f96a
Create Date: 2025-12-29 21:18:14.205122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16b8f13de9b6'
down_revision: Union[str, None] = 'a950af83f96a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add content_hash column for content-based deduplication
    op.add_column(
        'newsletters',
        sa.Column('content_hash', sa.String(64), nullable=True)
    )

    # Add canonical_newsletter_id to link duplicates to canonical version
    op.add_column(
        'newsletters',
        sa.Column('canonical_newsletter_id', sa.Integer, nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_newsletters_canonical_newsletter_id',
        'newsletters',
        'newsletters',
        ['canonical_newsletter_id'],
        ['id']
    )

    # Add index for faster duplicate lookups
    op.create_index(
        'ix_newsletters_content_hash',
        'newsletters',
        ['content_hash']
    )


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_newsletters_content_hash', 'newsletters')

    # Remove foreign key
    op.drop_constraint('fk_newsletters_canonical_newsletter_id', 'newsletters', type_='foreignkey')

    # Remove columns
    op.drop_column('newsletters', 'canonical_newsletter_id')
    op.drop_column('newsletters', 'content_hash')
