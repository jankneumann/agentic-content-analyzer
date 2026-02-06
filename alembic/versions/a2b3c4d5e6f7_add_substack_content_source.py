"""add_substack_content_source

Revision ID: a2b3c4d5e6f7
Revises: f9a8b7c6d5e5
Create Date: 2026-02-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f9a8b7c6d5e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'substack'")


def downgrade() -> None:
    # Enum value removal is not supported without recreating the type.
    pass
