"""create theme_analyses table

Revision ID: b159ceaf9494
Revises: f00ddf1d2b47
Create Date: 2026-04-02

Note: The original migration 59fbc6999804 was a no-op (pass in both
upgrade/downgrade). It's already in the chain, so we create a new
migration at the current head to actually create the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b159ceaf9494"
down_revision: str | None = "f00ddf1d2b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the enum type via raw SQL (idempotent — IF NOT EXISTS)
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE analysisstatus AS ENUM ('queued', 'running', 'completed', 'failed'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    op.create_table(
        "theme_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "completed",
                "failed",
                name="analysisstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("analysis_date", sa.DateTime(), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("themes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("total_themes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emerging_themes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("top_theme", sa.String(500), nullable=True),
        sa.Column("agent_framework", sa.String(100), nullable=False, server_default=""),
        sa.Column("model_used", sa.String(100), nullable=False, server_default=""),
        sa.Column("model_version", sa.String(20), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=True),
        sa.Column("cross_theme_insights", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(NOW() AT TIME ZONE 'utc')"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_theme_analyses_status", "theme_analyses", ["status"])
    op.create_index("ix_theme_analyses_analysis_date", "theme_analyses", ["analysis_date"])
    op.create_index("ix_theme_analyses_created_at", "theme_analyses", ["created_at"])
    op.create_index("ix_theme_analyses_status_created", "theme_analyses", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_theme_analyses_status_created", table_name="theme_analyses")
    op.drop_index("ix_theme_analyses_created_at", table_name="theme_analyses")
    op.drop_index("ix_theme_analyses_analysis_date", table_name="theme_analyses")
    op.drop_index("ix_theme_analyses_status", table_name="theme_analyses")
    op.drop_table("theme_analyses")

    # Drop the enum type
    sa.Enum(name="analysisstatus").drop(op.get_bind(), checkfirst=True)
