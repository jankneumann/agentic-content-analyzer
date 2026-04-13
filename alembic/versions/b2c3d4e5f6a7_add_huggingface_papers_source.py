"""Add huggingface_papers content source type

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11 10:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside a transaction.
    op.execute("COMMIT")
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'huggingface_papers'")
    op.execute("BEGIN")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
