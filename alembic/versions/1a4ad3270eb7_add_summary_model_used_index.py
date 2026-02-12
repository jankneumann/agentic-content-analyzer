"""add summary model used index

Revision ID: 1a4ad3270eb7
Revises: b8affd253096
Create Date: 2026-02-10 18:43:40.352432

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a4ad3270eb7'
down_revision: Union[str, Sequence[str], None] = 'b8affd253096'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index to Summary.model_used (if not exists)
    conn = op.get_bind()
    # Check if table exists first (for safety in some test envs)
    inspector = sa.inspect(conn)
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
    inspector = sa.inspect(conn)
    if not inspector.has_table('summaries'):
        return

    indexes = inspector.get_indexes('summaries')
    index_names = [i['name'] for i in indexes]

    if 'ix_summaries_model_used' in index_names:
        op.drop_index(op.f('ix_summaries_model_used'), table_name='summaries')
