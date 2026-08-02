"""Add the Obsidian Content source enum value.

Revision ID: b7d4f9a2c315
Revises: b1e5c7d9f204
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b7d4f9a2c315"
down_revision: str | None = "b1e5c7d9f204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the private Obsidian ingestion source identity."""

    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'obsidian'")


def downgrade() -> None:
    """No-op: PostgreSQL enum values cannot be safely removed in place."""

    pass
