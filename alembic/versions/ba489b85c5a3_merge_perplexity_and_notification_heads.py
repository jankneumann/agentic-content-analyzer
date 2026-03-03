"""merge perplexity and notification heads

Revision ID: ba489b85c5a3
Revises: 22d53edb2933, da8203070ef9
Create Date: 2026-02-27 15:54:58.745603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba489b85c5a3'
down_revision: Union[str, None] = ('22d53edb2933', 'da8203070ef9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
