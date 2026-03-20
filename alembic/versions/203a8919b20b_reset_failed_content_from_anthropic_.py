"""reset_failed_content_from_anthropic_routing_error

Data migration: Resets content items that failed due to the Anthropic-only
routing bug (before LLMRouter integration) back to 'pending' so they can
be re-processed through the now provider-agnostic pipeline.

Also cleans up associated failed jobs from the queue.

Revision ID: 203a8919b20b
Revises: c1d2e3f4a5b6
Create Date: 2026-03-19 18:04:25.696510

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '203a8919b20b'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Task 4.1: Reset content items that failed due to Anthropic-only routing
    op.execute(
        """
        UPDATE contents
        SET status = 'pending', error_message = NULL
        WHERE status = 'failed'
          AND error_message LIKE '%No Anthropic-compatible providers%'
        """
    )

    # Task 4.2: Clean up associated failed jobs from the queue
    op.execute(
        """
        DELETE FROM pgqueuer_jobs
        WHERE status = 'failed'
        """
    )


def downgrade() -> None:
    # Data migration — cannot meaningfully reverse.
    # The content items were broken before; resetting them to 'failed'
    # would re-break them without restoring the original error messages.
    pass
