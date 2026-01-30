"""Add summaries created_at index

Revision ID: c017a1a2b3c5
Revises: f2b3c4d5e6f7, b017a1a2b3c4
Create Date: 2026-01-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'c017a1a2b3c5'
down_revision: Union[str, Sequence[str], None] = ('f2b3c4d5e6f7', 'b017a1a2b3c4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Check if index exists on summaries table
    indexes = inspector.get_indexes('summaries')
    if not any(idx['name'] == 'ix_summaries_created_at' for idx in indexes):
        op.create_index(
            op.f('ix_summaries_created_at'),
            'summaries',
            ['created_at'],
            unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Drop index if exists
    indexes = inspector.get_indexes('summaries')
    if any(idx['name'] == 'ix_summaries_created_at' for idx in indexes):
        op.drop_index(op.f('ix_summaries_created_at'), table_name='summaries')
