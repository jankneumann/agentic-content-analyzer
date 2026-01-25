"""add_audio_digests_table

Creates the audio_digests table for tracking text-to-speech generation
of digest content. Supports multiple TTS providers (OpenAI, ElevenLabs, etc.)
with configurable voice and speed options.

Revision ID: c1d2e3f4g5h6
Revises: b846f2b0247c
Create Date: 2026-01-24 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4g5h6"
down_revision: Union[str, None] = "b846f2b0247c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum values for AudioDigestStatus
audio_digest_status_values = ["pending", "processing", "completed", "failed"]


def upgrade() -> None:
    """Create audio_digests table for tracking TTS generation."""
    conn = op.get_bind()

    # Check if enum type already exists (idempotent)
    result = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_type WHERE typname = 'audiodigeststatus'
            """
        )
    )
    if not result.fetchone():
        # Create PostgreSQL enum type for audio digest status
        op.execute(
            "CREATE TYPE audiodigeststatus AS ENUM ('pending', 'processing', 'completed', 'failed')"
        )

    # Check if table already exists (idempotent)
    result = conn.execute(
        sa.text(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'audio_digests'
            """
        )
    )
    if result.fetchone():
        # Table already exists
        return

    # Create audio_digests table
    op.create_table(
        "audio_digests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("digest_id", sa.Integer(), nullable=False),
        # Generation config
        sa.Column("voice", sa.String(length=50), nullable=False),
        sa.Column("speed", sa.Float(), server_default="1.0"),
        sa.Column("provider", sa.String(length=50), server_default="openai"),
        # Status tracking
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "failed",
                name="audiodigeststatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Output
        sa.Column("audio_url", sa.String(length=500), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        # Analytics
        sa.Column("text_char_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
        # Foreign key constraint
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["digests.id"],
            name="fk_audio_digests_digest_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes
    op.create_index("ix_audio_digests_digest_id", "audio_digests", ["digest_id"])
    op.create_index("ix_audio_digests_status", "audio_digests", ["status"])


def downgrade() -> None:
    """Drop audio_digests table and enum."""
    conn = op.get_bind()

    # Check if table exists before dropping
    result = conn.execute(
        sa.text(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'audio_digests'
            """
        )
    )
    if result.fetchone():
        # Drop indexes (use IF EXISTS via raw SQL for safety)
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_audio_digests_status"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_audio_digests_digest_id"))

        # Drop table
        op.drop_table("audio_digests")

    # Drop enum (IF EXISTS is already safe)
    op.execute("DROP TYPE IF EXISTS audiodigeststatus")
