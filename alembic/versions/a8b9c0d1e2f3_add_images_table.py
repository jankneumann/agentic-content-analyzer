"""add_images_table

Revision ID: a8b9c0d1e2f3
Revises: 7238482da990
Create Date: 2026-01-17 10:00:00.000000

This migration creates the images table to support:
- Extracted images from HTML/PDF content
- YouTube video keyframes (slide captures)
- AI-generated images (future feature)

The table uses a polymorphic source_type pattern and includes perceptual
hashing (phash) for deduplication across all image sources.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "7238482da990"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum values for ImageSource
image_source_values = [
    "extracted",  # Extracted from HTML/PDF content
    "keyframe",  # YouTube video keyframe (slide capture)
    "ai_generated",  # AI-generated image (future feature)
]


def upgrade() -> None:
    """Create images table for unified image storage."""
    # Create PostgreSQL enum type for image source
    op.execute(
        "CREATE TYPE imagesource AS ENUM ('extracted', 'keyframe', 'ai_generated')"
    )

    # Create images table
    op.create_table(
        "images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),

        # Source type (polymorphic discriminator)
        sa.Column(
            "source_type",
            postgresql.ENUM(*image_source_values, name="imagesource", create_type=False),
            nullable=False,
        ),

        # Foreign keys to source entities (nullable - only one should be set)
        sa.Column("source_content_id", sa.Integer(), nullable=True),
        sa.Column("source_summary_id", sa.Integer(), nullable=True),
        sa.Column("source_digest_id", sa.Integer(), nullable=True),

        # Original source information
        sa.Column("source_url", sa.String(length=2000), nullable=True),  # Original image URL

        # YouTube-specific metadata (for keyframes)
        sa.Column("video_id", sa.String(length=20), nullable=True),  # YouTube video ID
        sa.Column("timestamp_seconds", sa.Float(), nullable=True),  # Timestamp in video
        sa.Column("deep_link_url", sa.String(length=500), nullable=True),  # youtu.be/xxx?t=123

        # Storage information
        sa.Column("storage_path", sa.String(length=500), nullable=False),  # Relative path
        sa.Column("storage_provider", sa.String(length=50), nullable=False,
                  server_default="local"),  # "local", "s3"

        # Image metadata
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),

        # Descriptive metadata
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),  # AI-generated description

        # AI generation metadata (for source_type = 'ai_generated')
        sa.Column("generation_prompt", sa.Text(), nullable=True),
        sa.Column("generation_model", sa.String(length=100), nullable=True),
        sa.Column("generation_params", sa.JSON(), nullable=True),

        # Perceptual hash for deduplication
        sa.Column("phash", sa.String(length=64), nullable=True),

        # Timestamp
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),

        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_content_id"],
            ["contents.id"],
            name="fk_images_source_content_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_summary_id"],
            ["newsletter_summaries.id"],
            name="fk_images_source_summary_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_digest_id"],
            ["digests.id"],
            name="fk_images_source_digest_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes
    op.create_index("ix_images_source_type", "images", ["source_type"])
    op.create_index("ix_images_source_content_id", "images", ["source_content_id"])
    op.create_index("ix_images_source_summary_id", "images", ["source_summary_id"])
    op.create_index("ix_images_source_digest_id", "images", ["source_digest_id"])
    op.create_index("ix_images_phash", "images", ["phash"])
    op.create_index("ix_images_video_id", "images", ["video_id"])


def downgrade() -> None:
    """Drop images table and enum."""
    # Drop indexes
    op.drop_index("ix_images_video_id", table_name="images")
    op.drop_index("ix_images_phash", table_name="images")
    op.drop_index("ix_images_source_digest_id", table_name="images")
    op.drop_index("ix_images_source_summary_id", table_name="images")
    op.drop_index("ix_images_source_content_id", table_name="images")
    op.drop_index("ix_images_source_type", table_name="images")

    # Drop table
    op.drop_table("images")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS imagesource")
