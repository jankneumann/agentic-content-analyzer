"""Add xsearch to content_source enum.

Revision ID: d364355a18ba
Revises: 33072a43b224
Create Date: 2026-02-23

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d364355a18ba"
down_revision = "33072a43b224"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE is not transactional in PostgreSQL,
    # so we must run it outside a transaction block.
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'xsearch'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums.
    # The value will remain but be unused after downgrade.
    pass
