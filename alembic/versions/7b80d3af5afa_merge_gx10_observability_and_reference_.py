"""merge gx10 observability and reference expansion heads

Revision ID: 7b80d3af5afa
Revises: f3a91c5d7e28, f5c8d2b0e3a7
Create Date: 2026-10-21 14:40:30.689077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b80d3af5afa'
down_revision: Union[str, None] = ('f3a91c5d7e28', 'f5c8d2b0e3a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
