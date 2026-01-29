"""Add index to Summary.created_at

Revision ID: c028a1a2b3c5
Revises: b017a1a2b3c4
Create Date: 2026-01-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'c028a1a2b3c5'
down_revision: Union[str, None] = 'b017a1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use Inspector to check if index exists to make it idempotent
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    indexes = inspector.get_indexes('summaries')
    index_names = [idx['name'] for idx in indexes]

    if 'ix_summaries_created_at' not in index_names:
        op.create_index(
            op.f('ix_summaries_created_at'),
            'summaries',
            ['created_at'],
            unique=False
        )


def downgrade() -> None:
    # Use Inspector to check if index exists before dropping
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    indexes = inspector.get_indexes('summaries')
    index_names = [idx['name'] for idx in indexes]

    if 'ix_summaries_created_at' in index_names:
        op.drop_index(op.f('ix_summaries_created_at'), table_name='summaries')
