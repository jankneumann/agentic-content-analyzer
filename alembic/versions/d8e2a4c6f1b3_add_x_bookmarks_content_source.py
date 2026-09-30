"""Add the X bookmarks Content source enum value.

Revision ID: d8e2a4c6f1b3
Revises: c3f1a8b6e40d
Create Date: 2026-09-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d8e2a4c6f1b3"
down_revision: str | None = "c3f1a8b6e40d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the X bookmarks ingestion source identity."""

    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'x_bookmarks'")


def downgrade() -> None:
    """No-op: PostgreSQL enum values cannot be safely removed in place."""

    pass
