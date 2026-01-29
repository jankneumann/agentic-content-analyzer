"""Remove redundant indexes and merge heads

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6, e4f5a6b7c8d9, c1d2e3f4g5h6
Create Date: 2026-01-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = ('e1f2a3b4c5d6', 'e4f5a6b7c8d9', 'c1d2e3f4g5h6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop redundant indexes on contents table
    # These are redundant because:
    # 1. source_type is the first column of idx_contents_source (source_type, source_id)
    # 2. publication is the first column of idx_contents_publication_date (publication, published_date)

    # We drop them if they exist to avoid errors if they were already dropped or never created
    # However, standard alembic drop_index doesn't have if_exists, but these should exist based on history.
    op.drop_index('ix_contents_source_type', table_name='contents')
    op.drop_index('ix_contents_publication', table_name='contents')


def downgrade() -> None:
    # Re-create the indexes
    op.create_index('ix_contents_publication', 'contents', ['publication'], unique=False)
    op.create_index('ix_contents_source_type', 'contents', ['source_type'], unique=False)
