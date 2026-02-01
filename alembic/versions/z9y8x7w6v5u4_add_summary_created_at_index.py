"""Add index to Summary.created_at

Revision ID: z9y8x7w6v5u4
Revises: b017a1a2b3c4
Create Date: 2026-01-26 10:00:00.000000

"""
from collections.abc import Sequence

from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'z9y8x7w6v5u4'
down_revision: str | None = 'b017a1a2b3c4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Check if index exists
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
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Check if index exists before dropping
    indexes = inspector.get_indexes('summaries')
    index_names = [idx['name'] for idx in indexes]

    if 'ix_summaries_created_at' in index_names:
        op.drop_index(op.f('ix_summaries_created_at'), table_name='summaries')
