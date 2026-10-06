"""Mark source overrides written by an automated sync.

Revision ID: e4b7c1a9d2f6
Revises: d8e2a4c6f1b3
Create Date: 2026-09-30 00:00:00.000000

``managed_by`` names the automation that created a ``source_overrides`` row
(``substack-sync`` for ``aca sources sync substack``). Pruning only ever
touches rows carrying its own marker, so hand-made overrides are never pruned.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b7c1a9d2f6"
down_revision: str | None = "d8e2a4c6f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable managed_by marker."""

    op.add_column("source_overrides", sa.Column("managed_by", sa.String(64), nullable=True))


def downgrade() -> None:
    """Drop the marker; rows stay, now indistinguishable from hand-made ones."""

    op.drop_column("source_overrides", "managed_by")
