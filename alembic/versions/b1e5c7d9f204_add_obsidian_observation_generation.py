"""Add monotonic Obsidian observation generation.

Revision ID: b1e5c7d9f204
Revises: a6c3e8f1d204
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b1e5c7d9f204"
down_revision: str | None = "a6c3e8f1d204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE obsidian_ingest_state "
        "ADD COLUMN observation_generation BIGINT NOT NULL DEFAULT 0, "
        "ADD CONSTRAINT ck_obsidian_ingest_state_observation_generation "
        "CHECK (observation_generation >= 0)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE obsidian_ingest_state DROP COLUMN observation_generation")
