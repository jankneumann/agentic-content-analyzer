"""create theme_analyses table with status tracking

Revision ID: c1d2e3f4a5b6
Revises: ba489b85c5a3
Create Date: 2026-03-16 19:42:49.638536

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "ba489b85c5a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the analysisstatus enum type
    analysisstatus = sa.Enum(
        "queued", "running", "completed", "failed",
        name="analysisstatus",
    )
    analysisstatus.create(op.get_bind(), checkfirst=True)

    # Check if table already exists (idempotent)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'theme_analyses'"
        )
    )
    if result.fetchone():
        return

    op.create_table(
        "theme_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "completed", "failed", name="analysisstatus"),
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
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_theme_analyses_analysis_date", "theme_analyses", ["analysis_date"])
    op.create_index("ix_theme_analyses_status", "theme_analyses", ["status"])
    op.create_index("ix_theme_analyses_created_at", "theme_analyses", ["created_at"])
    op.create_index(
        "ix_theme_analyses_status_created", "theme_analyses", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("theme_analyses")
    sa.Enum(name="analysisstatus").drop(op.get_bind(), checkfirst=True)
