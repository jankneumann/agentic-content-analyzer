"""Add scholar content source and metadata_json GIN index

Revision ID: 2a0ca52d63c3
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2a0ca52d63c3"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'scholar' to the contentsource enum
    op.execute("ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'scholar'")

    # Add GIN index on metadata_json for efficient containment queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_metadata_json_gin "
        "ON contents USING GIN (metadata_json jsonb_path_ops)"
    )


def downgrade() -> None:
    # Drop the GIN index
    op.execute("DROP INDEX IF EXISTS ix_content_metadata_json_gin")

    # Note: PostgreSQL does not support removing values from an enum type.
    # The 'scholar' value will remain in the contentsource enum after downgrade.
