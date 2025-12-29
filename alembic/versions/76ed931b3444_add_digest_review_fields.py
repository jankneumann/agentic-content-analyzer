"""add_digest_review_fields

Revision ID: 76ed931b3444
Revises: d75166ebc782
Create Date: 2025-12-28 20:27:04.444609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76ed931b3444'
down_revision: Union[str, None] = 'd75166ebc782'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add review tracking fields to digests table."""
    # Add new columns
    op.add_column('digests',
        sa.Column('reviewed_by', sa.String(length=200), nullable=True))
    op.add_column('digests',
        sa.Column('review_notes', sa.Text(), nullable=True))
    op.add_column('digests',
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('digests',
        sa.Column('revision_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('digests',
        sa.Column('revision_history', sa.JSON(), nullable=True))

    # Update enum type to add new status values (PostgreSQL specific)
    # Note: Cannot use ALTER TYPE ADD VALUE in a transaction, so we use this approach
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'pending_review' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'digeststatus')) THEN
                ALTER TYPE digeststatus ADD VALUE 'pending_review';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'approved' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'digeststatus')) THEN
                ALTER TYPE digeststatus ADD VALUE 'approved';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'rejected' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'digeststatus')) THEN
                ALTER TYPE digeststatus ADD VALUE 'rejected';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Remove review tracking fields from digests table."""
    # Drop columns
    op.drop_column('digests', 'revision_history')
    op.drop_column('digests', 'revision_count')
    op.drop_column('digests', 'reviewed_at')
    op.drop_column('digests', 'review_notes')
    op.drop_column('digests', 'reviewed_by')

    # Note: Cannot easily remove enum values in PostgreSQL without recreating the type
    # This would require recreating all tables using the enum
    # For simplicity, we leave the enum values in place during downgrade
