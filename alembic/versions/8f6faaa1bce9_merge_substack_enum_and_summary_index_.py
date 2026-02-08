"""merge substack enum and summary index branches

Revision ID: 8f6faaa1bce9
Revises: 58aa2c7e188c, a2b3c4d5e6f7
Create Date: 2026-02-07 21:56:12.438677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f6faaa1bce9'
down_revision: Union[str, None] = ('58aa2c7e188c', 'a2b3c4d5e6f7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
