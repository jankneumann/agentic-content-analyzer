"""add_hierarchical_digest_support

Revision ID: a950af83f96a
Revises: 76ed931b3444
Create Date: 2025-12-29 10:32:50.314676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a950af83f96a'
down_revision: Union[str, None] = '76ed931b3444'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hierarchical digest support columns and enum value."""
    # Add new columns for hierarchical digest support
    op.add_column('digests',
        sa.Column('parent_digest_id', sa.Integer(), nullable=True))
    op.add_column('digests',
        sa.Column('child_digest_ids', sa.JSON(), nullable=True))
    op.add_column('digests',
        sa.Column('is_combined', sa.Integer(), server_default='0', nullable=False))
    op.add_column('digests',
        sa.Column('source_digest_count', sa.Integer(), nullable=True))

    # Create foreign key constraint for parent_digest_id
    op.create_foreign_key(
        'fk_digests_parent_digest_id',
        'digests', 'digests',
        ['parent_digest_id'], ['id'],
        ondelete='SET NULL'
    )

    # Create index on parent_digest_id for query performance
    op.create_index(
        'ix_digests_parent_digest_id',
        'digests',
        ['parent_digest_id'],
        unique=False
    )

    # Add SUB_DIGEST enum value to DigestType (PostgreSQL specific)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'sub_digest' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'digesttype')) THEN
                ALTER TYPE digesttype ADD VALUE 'sub_digest';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Remove hierarchical digest support columns."""
    # Drop index
    op.drop_index('ix_digests_parent_digest_id', table_name='digests')

    # Drop foreign key constraint
    op.drop_constraint('fk_digests_parent_digest_id', 'digests', type_='foreignkey')

    # Drop columns
    op.drop_column('digests', 'source_digest_count')
    op.drop_column('digests', 'is_combined')
    op.drop_column('digests', 'child_digest_ids')
    op.drop_column('digests', 'parent_digest_id')

    # Note: Cannot easily remove enum values in PostgreSQL without recreating the type
    # This would require recreating all tables using the enum
    # For simplicity, we leave the enum value in place during downgrade
