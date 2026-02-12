"""merge add-document-search with main

Revision ID: b8affd253096
Revises: 1fdacd9de420, b2c3d4e5f6a7
Create Date: 2026-02-10 22:18:52.498328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8affd253096'
down_revision: Union[str, None] = ('1fdacd9de420', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
