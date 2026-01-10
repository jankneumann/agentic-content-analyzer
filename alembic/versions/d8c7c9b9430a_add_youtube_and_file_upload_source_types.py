"""add_youtube_and_file_upload_source_types

Revision ID: d8c7c9b9430a
Revises: 3697508e93f1
Create Date: 2026-01-10 17:27:31.621613

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8c7c9b9430a"
down_revision: Union[str, None] = "3697508e93f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add YOUTUBE and FILE_UPLOAD to newslettersource enum."""
    connection = op.get_bind()

    # Check if YOUTUBE value already exists
    youtube_exists = connection.execute(
        sa.text("""
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'YOUTUBE'
        AND enumtypid = (
            SELECT oid FROM pg_type WHERE typname = 'newslettersource'
        )
    """)
    ).fetchone()

    if not youtube_exists:
        # Add the enum value outside of transaction
        connection.execute(sa.text("COMMIT"))
        connection.execute(sa.text("ALTER TYPE newslettersource ADD VALUE 'YOUTUBE'"))
        connection.execute(sa.text("BEGIN"))

    # Check if FILE_UPLOAD value already exists
    file_upload_exists = connection.execute(
        sa.text("""
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'FILE_UPLOAD'
        AND enumtypid = (
            SELECT oid FROM pg_type WHERE typname = 'newslettersource'
        )
    """)
    ).fetchone()

    if not file_upload_exists:
        # Add the enum value outside of transaction
        connection.execute(sa.text("COMMIT"))
        connection.execute(
            sa.text("ALTER TYPE newslettersource ADD VALUE 'FILE_UPLOAD'")
        )
        connection.execute(sa.text("BEGIN"))


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL - no-op."""
    # Note: PostgreSQL does not support removing enum values
    # The YOUTUBE and FILE_UPLOAD values will remain in the enum
    pass
