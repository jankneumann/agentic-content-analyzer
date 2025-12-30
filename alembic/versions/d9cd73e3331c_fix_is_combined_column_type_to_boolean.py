"""fix is_combined column type to boolean

Revision ID: d9cd73e3331c
Revises: 16b8f13de9b6
Create Date: 2025-12-29 22:44:53.252605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9cd73e3331c'
down_revision: Union[str, None] = '16b8f13de9b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change is_combined column from integer to boolean."""
    # PostgreSQL: Multi-step conversion
    # 1. Drop the default
    op.execute("""
        ALTER TABLE digests
        ALTER COLUMN is_combined DROP DEFAULT
    """)

    # 2. Convert column type from integer to boolean
    op.execute("""
        ALTER TABLE digests
        ALTER COLUMN is_combined TYPE BOOLEAN
        USING is_combined::boolean
    """)

    # 3. Set new boolean default
    op.execute("""
        ALTER TABLE digests
        ALTER COLUMN is_combined SET DEFAULT false
    """)


def downgrade() -> None:
    """Revert is_combined column from boolean to integer."""
    # PostgreSQL: Multi-step conversion
    # 1. Drop the default
    op.execute("""
        ALTER TABLE digests
        ALTER COLUMN is_combined DROP DEFAULT
    """)

    # 2. Convert boolean to integer (0/1)
    op.execute("""
        ALTER TABLE digests
        ALTER COLUMN is_combined TYPE INTEGER
        USING CASE WHEN is_combined THEN 1 ELSE 0 END
    """)

    # 3. Set integer default
    op.execute("""
        ALTER TABLE digests
        ALTER COLUMN is_combined SET DEFAULT 0
    """)
