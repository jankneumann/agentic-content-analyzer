"""Add summary model_used index

Revision ID: f2a3b4c5d6e7
Revises: f9a8b7c6d5e5, e1f2a3b4c5d6
Create Date: 2026-02-17 10:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = ('f9a8b7c6d5e5', 'e1f2a3b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index to Summary.model_used (if not exists)
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    # Check if table exists first (for safety in some test envs)
    if not inspector.has_table('summaries'):
        return

    indexes = inspector.get_indexes('summaries')
    index_names = [i['name'] for i in indexes]

    if 'ix_summaries_model_used' not in index_names:
        op.create_index(
            op.f('ix_summaries_model_used'),
            'summaries',
            ['model_used'],
            unique=False
        )


def downgrade() -> None:
    # Drop index from Summary.model_used (if exists)
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if not inspector.has_table('summaries'):
        return

    indexes = inspector.get_indexes('summaries')
    index_names = [i['name'] for i in indexes]

    if 'ix_summaries_model_used' in index_names:
        op.drop_index(op.f('ix_summaries_model_used'), table_name='summaries')
