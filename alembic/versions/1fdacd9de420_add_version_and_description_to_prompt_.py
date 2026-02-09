"""add_version_and_description_to_prompt_overrides

Revision ID: 1fdacd9de420
Revises: 8f6faaa1bce9
Create Date: 2026-02-08 16:46:25.089214

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1fdacd9de420"
down_revision: Union[str, None] = "8f6faaa1bce9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prompt_overrides",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "prompt_overrides",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prompt_overrides", "description")
    op.drop_column("prompt_overrides", "version")
