"""Add perplexity to content_source enum.

Revision ID: 22d53edb2933
Revises: d364355a18ba
Create Date: 2026-02-24

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "22d53edb2933"
down_revision = "d364355a18ba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE is not transactional in PostgreSQL,
    # so we must run it outside a transaction block.
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'perplexity'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums.
    # The value will remain but be unused after downgrade.
    pass
