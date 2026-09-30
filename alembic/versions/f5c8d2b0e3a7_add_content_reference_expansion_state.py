"""Track linked-article expansion on content references.

Revision ID: f5c8d2b0e3a7
Revises: e4b7c1a9d2f6
Create Date: 2026-09-30 00:00:00.000000

``expansion_state`` records what X bookmark link expansion did with a
reference's link (``pending``, ``submitted``, ``skipped``, ``failed``); NULL
means the reference is not an expansion candidate, so references from
newsletters and every other source are unaffected. ``expansion_attempts``
counts failed-or-successful submissions and ``expansion_attempted_at`` stamps
the last one. The partial index serves the retry pass, which reads the oldest
``pending``/``failed`` references first.

Existing references of ``x_bookmarks`` rows are backfilled to ``pending``; the
first retry pass marks the ones already stored (or feed/playlist links) as
``skipped``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5c8d2b0e3a7"
down_revision: str | None = "e4b7c1a9d2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "content_references"
RETRY_INDEX = "ix_content_refs_expansion_retry"
STATE_CHECK = "chk_content_refs_expansion_state"
ATTEMPTS_CHECK = "chk_content_refs_expansion_attempts"


def upgrade() -> None:
    """Add the expansion state columns, their CHECKs, the retry index, and backfill."""

    op.add_column(TABLE, sa.Column("expansion_state", sa.String(16), nullable=True))
    op.add_column(
        TABLE,
        sa.Column(
            "expansion_attempts",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        TABLE, sa.Column("expansion_attempted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        STATE_CHECK,
        TABLE,
        "expansion_state IS NULL OR expansion_state IN ('pending', 'submitted', 'skipped', 'failed')",
    )
    op.create_check_constraint(
        ATTEMPTS_CHECK,
        TABLE,
        "expansion_attempts >= 0 AND expansion_attempts <= 100",
    )
    op.create_index(
        RETRY_INDEX,
        TABLE,
        ["created_at"],
        postgresql_where=sa.text("expansion_state IN ('pending', 'failed')"),
    )
    # source_type is compared as text: a fresh database adds the enum value
    # earlier in this same transaction, and PostgreSQL rejects a new enum value
    # used as a literal before that transaction commits.
    op.execute(
        "UPDATE content_references AS ref SET expansion_state = 'pending' "
        "FROM contents AS c "
        "WHERE c.id = ref.source_content_id "
        "AND c.source_type::text = 'x_bookmarks' "
        "AND ref.external_url IS NOT NULL "
        "AND ref.expansion_state IS NULL"
    )


def downgrade() -> None:
    """Drop the index, CHECKs, and columns; the references themselves stay."""

    op.drop_index(RETRY_INDEX, table_name=TABLE)
    op.drop_constraint(ATTEMPTS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATE_CHECK, TABLE, type_="check")
    op.drop_column(TABLE, "expansion_attempted_at")
    op.drop_column(TABLE, "expansion_attempts")
    op.drop_column(TABLE, "expansion_state")
