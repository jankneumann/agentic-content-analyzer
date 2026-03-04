"""merge_heads

Revision ID: a23a53ea737b
Revises: b1b2c3d4e5f6, da8203070ef9
Create Date: 2026-03-01 20:17:09.728238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a23a53ea737b'
down_revision: Union[str, None] = ('b1b2c3d4e5f6', 'da8203070ef9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
