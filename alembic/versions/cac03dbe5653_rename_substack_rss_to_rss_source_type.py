"""rename substack_rss to rss source type

Revision ID: cac03dbe5653
Revises: d9cd73e3331c
Create Date: 2025-12-30 20:12:48.068684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cac03dbe5653'
down_revision: Union[str, None] = 'd9cd73e3331c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename SUBSTACK_RSS source type to RSS."""
    # Step 1: Add 'RSS' (uppercase) to the enum type if not already there
    # PostgreSQL doesn't have IF NOT EXISTS for enum values, so we use a workaround
    # Note: This must be executed outside a transaction block
    connection = op.get_bind()

    # Check if RSS value already exists
    result = connection.execute(sa.text("""
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'RSS'
        AND enumtypid = (
            SELECT oid FROM pg_type WHERE typname = 'newslettersource'
        )
    """)).fetchone()

    if not result:
        # Add the enum value outside of transaction
        # We need to commit the current transaction first
        connection.execute(sa.text("COMMIT"))
        connection.execute(sa.text("ALTER TYPE newslettersource ADD VALUE 'RSS'"))
        # Start a new transaction
        connection.execute(sa.text("BEGIN"))

    # Step 2: Update all newsletters with source 'SUBSTACK_RSS' (uppercase) to 'RSS' (uppercase)
    op.execute("""
        UPDATE newsletters
        SET source = 'RSS'
        WHERE source = 'SUBSTACK_RSS'
    """)


def downgrade() -> None:
    """Revert RSS source type back to SUBSTACK_RSS."""
    # Revert all newsletters with source 'RSS' back to 'SUBSTACK_RSS'
    # Note: We cannot remove enum values in PostgreSQL, so 'RSS' will remain in the enum
    op.execute("""
        UPDATE newsletters
        SET source = 'SUBSTACK_RSS'
        WHERE source = 'RSS'
    """)
