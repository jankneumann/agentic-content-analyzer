"""Add source_overrides table

Database-backed ingestion source overrides, merged on top of sources.d/ YAML
defaults by load_sources_config(). Mirrors the idempotent creation pattern used
by the settings_overrides table (b1c2d3e4f5a6).

Revision ID: c3d4e5f6a7b8
Revises: b8f8b5ededed
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b8f8b5ededed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (idempotent — same guard as settings_overrides)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'source_overrides')"
        )
    )
    if result.scalar():
        return

    op.create_table(
        "source_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_overrides_source_key", "source_overrides", ["source_key"], unique=True
    )
    op.create_index(
        "ix_source_overrides_source_type", "source_overrides", ["source_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_source_overrides_source_type", table_name="source_overrides")
    op.drop_index("ix_source_overrides_source_key", table_name="source_overrides")
    op.drop_table("source_overrides")
