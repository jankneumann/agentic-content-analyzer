"""add sharing fields to content summary digest

Revision ID: 33072a43b224
Revises: 718414e9009f
Create Date: 2026-02-22 13:39:08.253093

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "33072a43b224"
down_revision: str | None = "718414e9009f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that get sharing fields
_TABLES = ("contents", "summaries", "digests")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _TABLES:
        if table not in inspector.get_table_names():
            continue

        columns = {col["name"] for col in inspector.get_columns(table)}

        if "is_public" not in columns:
            op.add_column(
                table,
                sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
            )

        if "share_token" not in columns:
            op.add_column(
                table,
                sa.Column("share_token", sa.String(36), nullable=True),
            )
            # Partial unique index — only index non-null tokens
            op.create_index(
                f"idx_{table}_share_token",
                table,
                ["share_token"],
                unique=True,
                postgresql_where=sa.text("share_token IS NOT NULL"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _TABLES:
        if table not in inspector.get_table_names():
            continue

        columns = {col["name"] for col in inspector.get_columns(table)}

        if "share_token" in columns:
            op.drop_index(f"idx_{table}_share_token", table_name=table)
            op.drop_column(table, "share_token")

        if "is_public" in columns:
            op.drop_column(table, "is_public")
