"""add_summary_created_at_index

Revision ID: 58aa2c7e188c
Revises: f9a8b7c6d5e4
Create Date: 2026-02-02 18:37:06.536557

"""
from collections.abc import Sequence

from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '58aa2c7e188c'
down_revision: str | None = 'f9a8b7c6d5e4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Make migration idempotent - check if indexes exist before creating
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    indexes = inspector.get_indexes('summaries')
    index_names = [i['name'] for i in indexes]

    if 'ix_summaries_created_at' not in index_names:
        op.create_index(
            op.f('ix_summaries_created_at'),
            'summaries',
            ['created_at'],
            unique=False
        )


def downgrade() -> None:
    # Make migration idempotent - check if indexes exist before dropping
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    indexes = inspector.get_indexes('summaries')
    index_names = [i['name'] for i in indexes]

    if 'ix_summaries_created_at' in index_names:
        op.drop_index(op.f('ix_summaries_created_at'), table_name='summaries')
