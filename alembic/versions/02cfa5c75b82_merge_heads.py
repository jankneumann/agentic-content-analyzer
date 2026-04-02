"""merge_heads

Revision ID: 02cfa5c75b82
Revises: a1b2c3d4e5f9, c4d5e6f7a8b9
Create Date: 2026-04-02 05:51:29.393795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02cfa5c75b82'
down_revision: Union[str, None] = ('a1b2c3d4e5f9', 'c4d5e6f7a8b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
