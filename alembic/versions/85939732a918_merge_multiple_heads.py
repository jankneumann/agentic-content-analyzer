"""merge multiple heads

Revision ID: 85939732a918
Revises: a1b2c3d4e5f6, da8203070ef9
Create Date: 2026-03-01 19:58:52.970112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85939732a918'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'da8203070ef9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
