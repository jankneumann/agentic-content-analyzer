"""Add performance indexes

Revision ID: e1f2a3b4c5d6
Revises: f1a2b3c4d5e6
Create Date: 2026-01-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index to Content.ingested_at
    op.create_index(
        op.f('ix_contents_ingested_at'),
        'contents',
        ['ingested_at'],
        unique=False
    )

    # Add index to Digest.created_at
    op.create_index(
        op.f('ix_digests_created_at'),
        'digests',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    # Drop index from Digest.created_at
    op.drop_index(op.f('ix_digests_created_at'), table_name='digests')

    # Drop index from Content.ingested_at
    op.drop_index(op.f('ix_contents_ingested_at'), table_name='contents')
