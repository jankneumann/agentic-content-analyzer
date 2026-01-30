"""Add podcast content source enum value.

Revision ID: c2d3e4f5a6b7
Revises: b017a1a2b3c4
Create Date: 2026-01-29 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b017a1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'podcast' to the contentsource enum type."""
    # PostgreSQL requires ALTER TYPE to add new enum values.
    # IF NOT EXISTS makes this idempotent.
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'podcast'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values - no-op."""
    pass
