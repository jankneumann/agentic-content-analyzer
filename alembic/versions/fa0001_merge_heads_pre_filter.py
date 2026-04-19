"""Merge heads before ingestion filtering feature.

Revision ID: fa0001merge01
Revises: b2c3d4e5f6a7, c5f6a7b8d9e0
Create Date: 2026-04-19 09:00:00.000000

Merges the two pre-existing heads so the ingestion-filtering migration chain
has a single parent. No schema changes here — purely an alembic topology fix.
"""

from typing import Sequence, Union


revision: str = "fa0001merge01"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "c5f6a7b8d9e0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
