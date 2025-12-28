"""add_model_version_fields

Revision ID: d75166ebc782
Revises: 59fbc6999804
Create Date: 2025-12-28 18:18:10.170783

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd75166ebc782'
down_revision: Union[str, None] = '59fbc6999804'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add model_version column to tables that track model usage."""
    # Add model_version column to newsletter_summaries
    op.add_column('newsletter_summaries',
        sa.Column('model_version', sa.String(length=20), nullable=True)
    )

    # Add model_version column to digests
    op.add_column('digests',
        sa.Column('model_version', sa.String(length=20), nullable=True)
    )

    # Add model_version column to theme_analyses
    op.add_column('theme_analyses',
        sa.Column('model_version', sa.String(length=20), nullable=True)
    )

    # Migrate existing data: extract version from model_used and update to family-based ID
    # Pattern: claude-sonnet-4-5-20250929 -> model_used="claude-sonnet-4-5", model_version="20250929"

    # Update newsletter_summaries
    op.execute("""
        UPDATE newsletter_summaries
        SET model_version = substring(model_used from '(\\d{8})$'),
            model_used = regexp_replace(model_used, '-\\d{8}$', '')
        WHERE model_used ~ '\\d{8}$'
    """)

    # Update digests
    op.execute("""
        UPDATE digests
        SET model_version = substring(model_used from '(\\d{8})$'),
            model_used = regexp_replace(model_used, '-\\d{8}$', '')
        WHERE model_used ~ '\\d{8}$'
    """)

    # Update theme_analyses
    op.execute("""
        UPDATE theme_analyses
        SET model_version = substring(model_used from '(\\d{8})$'),
            model_used = regexp_replace(model_used, '-\\d{8}$', '')
        WHERE model_used ~ '\\d{8}$'
    """)


def downgrade() -> None:
    """Remove model_version column and restore old model_used format."""
    # Concatenate model_used and model_version back together
    # Example: model_used="claude-sonnet-4-5", model_version="20250929" -> "claude-sonnet-4-5-20250929"

    # newsletter_summaries
    op.execute("""
        UPDATE newsletter_summaries
        SET model_used = model_used || '-' || model_version
        WHERE model_version IS NOT NULL
    """)

    # digests
    op.execute("""
        UPDATE digests
        SET model_used = model_used || '-' || model_version
        WHERE model_version IS NOT NULL
    """)

    # theme_analyses
    op.execute("""
        UPDATE theme_analyses
        SET model_used = model_used || '-' || model_version
        WHERE model_version IS NOT NULL
    """)

    # Drop columns
    op.drop_column('newsletter_summaries', 'model_version')
    op.drop_column('digests', 'model_version')
    op.drop_column('theme_analyses', 'model_version')
