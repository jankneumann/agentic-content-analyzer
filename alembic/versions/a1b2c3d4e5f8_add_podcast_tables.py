"""add_podcast_tables

Revision ID: a1b2c3d4e5f6
Revises: 2969e6a07e38
Create Date: 2025-12-31 10:00:00.000000

Adds podcast_scripts and podcasts tables for digest-to-audio conversion feature.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f8"
down_revision: Union[str, None] = "2969e6a07e38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create podcast_scripts and podcasts tables."""

    # Create podcast_scripts table
    op.create_table(
        "podcast_scripts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("digest_id", sa.Integer(), nullable=False),
        sa.Column(
            "length",
            sa.Enum("brief", "standard", "extended", name="podcastlength"),
            nullable=False,
        ),
        # Script content
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("script_json", sa.JSON(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True),
        # Review workflow
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "script_generating",
                "script_pending_review",
                "script_revision_requested",
                "script_approved",
                "audio_generating",
                "completed",
                "failed",
                name="podcaststatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("revision_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revision_history", sa.JSON(), nullable=True),
        # Context & Tool Usage Tracking
        sa.Column("newsletter_ids_available", sa.JSON(), nullable=True),
        sa.Column("newsletter_ids_fetched", sa.JSON(), nullable=True),
        sa.Column("theme_ids", sa.JSON(), nullable=True),
        sa.Column("web_search_queries", sa.JSON(), nullable=True),
        sa.Column("tool_call_count", sa.Integer(), nullable=True),
        # Generation metadata
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("processing_time_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        # Primary key and foreign key
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_podcast_scripts_digest_id", "podcast_scripts", ["digest_id"])
    op.create_index("ix_podcast_scripts_status", "podcast_scripts", ["status"])

    # Create podcasts table
    op.create_table(
        "podcasts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("script_id", sa.Integer(), nullable=False),
        # Audio output
        sa.Column("audio_url", sa.String(length=1000), nullable=True),
        sa.Column("audio_format", sa.String(length=20), server_default="mp3", nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        # Voice configuration
        sa.Column(
            "voice_provider",
            sa.Enum("elevenlabs", "google_tts", "aws_polly", "openai_tts", name="voiceprovider"),
            nullable=True,
        ),
        sa.Column(
            "alex_voice",
            sa.Enum("alex_male", "alex_female", "sam_male", "sam_female", name="voicepersona"),
            nullable=True,
        ),
        sa.Column(
            "sam_voice",
            sa.Enum("alex_male", "alex_female", "sam_male", "sam_female", name="voicepersona"),
            nullable=True,
        ),
        sa.Column("voice_config", sa.JSON(), nullable=True),
        # Status
        sa.Column("status", sa.String(length=50), server_default="generating", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        # Primary key and foreign key
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["script_id"], ["podcast_scripts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_podcasts_script_id", "podcasts", ["script_id"])


def downgrade() -> None:
    """Drop podcast_scripts and podcasts tables."""

    # Drop podcasts table first (has FK to podcast_scripts)
    op.drop_index("ix_podcasts_script_id", table_name="podcasts")
    op.drop_table("podcasts")

    # Drop podcast_scripts table
    op.drop_index("ix_podcast_scripts_status", table_name="podcast_scripts")
    op.drop_index("ix_podcast_scripts_digest_id", table_name="podcast_scripts")
    op.drop_table("podcast_scripts")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS voicepersona")
    op.execute("DROP TYPE IF EXISTS voiceprovider")
    op.execute("DROP TYPE IF EXISTS podcaststatus")
    op.execute("DROP TYPE IF EXISTS podcastlength")
