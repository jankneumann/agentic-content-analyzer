"""Move YouTube metadata from links_json to metadata_json

During the migration to the unified Content model, YouTube transcript metadata
was incorrectly stored in links_json instead of metadata_json. This migration
moves that data to the correct field.

Revision ID: 7238482da990
Revises: 5a65cf4fe7b6
Create Date: 2026-01-12 15:43:50.462630

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7238482da990'
down_revision: Union[str, None] = '5a65cf4fe7b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Move links_json to metadata_json for YouTube content where:
    # - source_type is 'youtube'
    # - links_json is an object (not array or null)
    # - metadata_json is null
    op.execute("""
        UPDATE contents
        SET
            metadata_json = links_json,
            links_json = NULL
        WHERE
            source_type = 'youtube'
            AND json_typeof(links_json) = 'object'
            AND metadata_json IS NULL
    """)


def downgrade() -> None:
    # Move metadata_json back to links_json for YouTube content
    op.execute("""
        UPDATE contents
        SET
            links_json = metadata_json,
            metadata_json = NULL
        WHERE
            source_type = 'youtube'
            AND json_typeof(metadata_json) = 'object'
            AND links_json IS NULL
    """)
