"""Merge heads and remove redundant indexes

Revision ID: f9a8b7c6d5e4
Revises: c2d3e4f5a6b7, f1a2b3c4d5e6
Create Date: 2026-01-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'f9a8b7c6d5e4'
down_revision: Union[str, None] = ('c2d3e4f5a6b7', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop redundant indexes on contents table
    # These are redundant because:
    # 1. source_type is the first column of idx_contents_source (source_type, source_id)
    # 2. publication is the first column of idx_contents_publication_date (publication, published_date)

    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    indexes = inspector.get_indexes('contents')
    index_names = [i['name'] for i in indexes]

    if 'ix_contents_source_type' in index_names:
        op.drop_index('ix_contents_source_type', table_name='contents')

    if 'ix_contents_publication' in index_names:
        op.drop_index('ix_contents_publication', table_name='contents')


def downgrade() -> None:
    # Re-create the indexes
    op.create_index('ix_contents_publication', 'contents', ['publication'], unique=False)
    op.create_index('ix_contents_source_type', 'contents', ['source_type'], unique=False)
