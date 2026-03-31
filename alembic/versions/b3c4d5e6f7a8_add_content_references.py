"""Add content_references table

Revision ID: b3c4d5e6f7a8
Revises: 2a0ca52d63c3
Create Date: 2026-03-28 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "2a0ca52d63c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure metadata_json is JSONB (may already be if scholar migration ran)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='contents' AND column_name='metadata_json'"
        )
    )
    row = result.fetchone()
    if row and row[0] != "jsonb":
        op.execute("ALTER TABLE contents ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb")

    # 2. Create content_references table
    op.create_table(
        "content_references",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_content_id",
            sa.Integer(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reference_type", sa.String(20), nullable=False, server_default="cites"),
        sa.Column(
            "target_content_id",
            sa.Integer(),
            sa.ForeignKey("contents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("external_id_type", sa.String(20), nullable=True),
        sa.Column("resolution_status", sa.String(20), nullable=False, server_default="unresolved"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source_chunk_id",
            sa.Integer(),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context_snippet", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # CHECK constraint: must have at least one identifier
        sa.CheckConstraint(
            "external_id IS NOT NULL OR external_url IS NOT NULL",
            name="chk_has_identifier",
        ),
        # Unique constraint on (source_content_id, external_id, external_id_type)
        sa.UniqueConstraint(
            "source_content_id",
            "external_id",
            "external_id_type",
            name="uq_content_reference",
        ),
    )

    # 3. Create indexes
    op.create_index("ix_content_refs_source", "content_references", ["source_content_id"])
    op.execute(
        "CREATE INDEX ix_content_refs_target ON content_references (target_content_id) "
        "WHERE target_content_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_content_refs_external_id ON content_references (external_id_type, external_id) "
        "WHERE external_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_content_refs_unresolved ON content_references (resolution_status) "
        "WHERE resolution_status = 'unresolved'"
    )

    # 4. Partial unique index for URL-only references (no external_id)
    op.execute(
        "CREATE UNIQUE INDEX uq_content_reference_url ON content_references "
        "(source_content_id, external_url) WHERE external_id IS NULL"
    )

    # 5. GIN index on contents.metadata_json (idempotent)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_metadata_json_gin "
        "ON contents USING GIN (metadata_json jsonb_path_ops)"
    )


def downgrade() -> None:
    # Drop indexes and table (don't revert jsonb->json since shared with scholar migration)
    op.execute("DROP INDEX IF EXISTS ix_content_metadata_json_gin")
    op.execute("DROP INDEX IF EXISTS uq_content_reference_url")
    op.execute("DROP INDEX IF EXISTS ix_content_refs_unresolved")
    op.execute("DROP INDEX IF EXISTS ix_content_refs_external_id")
    op.execute("DROP INDEX IF EXISTS ix_content_refs_target")
    op.execute("DROP INDEX IF EXISTS ix_content_refs_source")
    op.drop_table("content_references")
