"""merge main and pgqueuer reliability heads

Revision ID: 718414e9009f
Revises: 6b7c8d9e0f1a, b1c2d3e4f5a6
Create Date: 2026-02-20 20:45:26.454547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '718414e9009f'
down_revision: Union[str, None] = ('6b7c8d9e0f1a', 'b1c2d3e4f5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
