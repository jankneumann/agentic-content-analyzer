"""Add blog content source type.

Revision ID: a1b2c3d4e5f6
Revises: 203a8919b20b
Create Date: 2026-03-25
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "203a8919b20b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'blog'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    # The 'blog' value will remain but be unused after downgrade
    pass
