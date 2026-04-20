"""Add huggingface_papers content source type

Revision ID: 1455833d558b
Revises: c5f6a7b8d9e0
Create Date: 2026-04-11 10:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "1455833d558b"
down_revision = "c5f6a7b8d9e0"
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
