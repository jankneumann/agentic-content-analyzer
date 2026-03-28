"""Add arxiv source type, jsonb migration, and GIN index

Revision ID: a1b2c3d4e5f6
Revises: f9a8b7c6d5e5
Create Date: 2026-03-28 12:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f9a8b7c6d5e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside a transaction.
    # We must commit any open transaction first, then execute outside it.
    op.execute("COMMIT")
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'arxiv'")
    op.execute("BEGIN")

    # Ensure metadata_json is jsonb (required for GIN index and @> containment)
    op.execute(
        "ALTER TABLE contents "
        "ALTER COLUMN metadata_json TYPE jsonb "
        "USING metadata_json::jsonb"
    )

    # GIN index for cross-source dedup via metadata_json @> containment queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_metadata_json_gin "
        "ON contents USING GIN (metadata_json jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_content_metadata_json_gin")
    # Note: ALTER TYPE DROP VALUE is not supported in PostgreSQL.
    # The 'arxiv' enum value will remain but be unused after downgrade.
    # jsonb -> json conversion is lossy for some edge cases, skip it.
