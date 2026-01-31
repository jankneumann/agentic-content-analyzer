"""Add index to Summary.created_at

Revision ID: g1a2b3c4d5e6
Revises: b017a1a2b3c4, f2a2b3c4d5e6
Create Date: 2026-01-26 10:00:00.000000

"""
from collections.abc import Sequence

from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'g1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = ('b017a1a2b3c4', 'f2a2b3c4d5e6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if index already exists (idempotent)
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    # Check if table exists first to be safe, though it should
    tables = inspector.get_table_names()
    if 'summaries' not in tables:
        return

    indexes = inspector.get_indexes('summaries')
    if not any(idx['name'] == 'ix_summaries_created_at' for idx in indexes):
        op.create_index(
            op.f('ix_summaries_created_at'),
            'summaries',
            ['created_at'],
            unique=False
        )


def downgrade() -> None:
    # Check if index exists before dropping
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if 'summaries' not in tables:
        return

    indexes = inspector.get_indexes('summaries')
    if any(idx['name'] == 'ix_summaries_created_at' for idx in indexes):
        op.drop_index(op.f('ix_summaries_created_at'), table_name='summaries')
