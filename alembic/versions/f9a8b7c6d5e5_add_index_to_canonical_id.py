"""Add index to canonical_id

Revision ID: f9a8b7c6d5e5
Revises: f9a8b7c6d5e4
Create Date: 2026-01-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'f9a8b7c6d5e5'
down_revision: Union[str, None] = 'f9a8b7c6d5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index to Content.canonical_id (if not exists)
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    indexes = inspector.get_indexes('contents')
    index_names = [i['name'] for i in indexes]

    if 'ix_contents_canonical_id' not in index_names:
        op.create_index(
            op.f('ix_contents_canonical_id'),
            'contents',
            ['canonical_id'],
            unique=False
        )


def downgrade() -> None:
    # Drop index from Content.canonical_id (if exists)
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    indexes = inspector.get_indexes('contents')
    index_names = [i['name'] for i in indexes]

    if 'ix_contents_canonical_id' in index_names:
        op.drop_index(op.f('ix_contents_canonical_id'), table_name='contents')
