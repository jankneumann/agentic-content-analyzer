"""add_prompt_overrides_table

Revision ID: 3697508e93f1
Revises: 7852b615ddcc
Create Date: 2026-01-08 12:43:47.159032

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3697508e93f1"
down_revision: Union[str, None] = "7852b615ddcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add prompt_overrides table for user customizations of default prompts."""
    op.create_table(
        "prompt_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prompt_overrides_key"), "prompt_overrides", ["key"], unique=True
    )


def downgrade() -> None:
    """Remove prompt_overrides table."""
    op.drop_index(op.f("ix_prompt_overrides_key"), table_name="prompt_overrides")
    op.drop_table("prompt_overrides")
