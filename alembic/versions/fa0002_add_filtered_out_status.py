"""Add FILTERED_OUT value to content_status enum.

Revision ID: fa0002filter01
Revises: fa0001merge01
Create Date: 2026-04-19 09:05:00.000000

Standalone migration — ALTER TYPE ADD VALUE cannot run inside a transaction
block alongside other DDL (CLAUDE.md gotcha #2). Keep this migration isolated
from the column additions that follow.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "fa0002filter01"
down_revision: Union[str, None] = "fa0001merge01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'filtered_out'")


def downgrade() -> None:
    raise NotImplementedError(
        "Removing an enum value is not supported by Postgres without a full type rebuild. "
        "To revert, restore from backup or manually rebuild the contentstatus type."
    )
