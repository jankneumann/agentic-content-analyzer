"""Add tree index columns to document_chunks

Adds parent_chunk_id (self-referential FK with CASCADE), tree_depth, and
is_summary columns for hierarchical tree index support. All nullable to
preserve compatibility with existing flat chunks.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-30 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tree index columns (all nullable — flat chunks remain unchanged)
    op.add_column(
        "document_chunks",
        sa.Column("parent_chunk_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("tree_depth", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("is_summary", sa.Boolean(), nullable=True, server_default="false"),
    )

    # Self-referential FK with CASCADE delete (tree cleanup)
    op.create_foreign_key(
        "fk_chunk_parent",
        "document_chunks",
        "document_chunks",
        ["parent_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Index for parent lookups
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
    )

    # Composite index for tree structure queries
    op.create_index(
        "ix_document_chunks_content_tree",
        "document_chunks",
        ["content_id", "tree_depth"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_tree", table_name="document_chunks")
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_constraint("fk_chunk_parent", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "is_summary")
    op.drop_column("document_chunks", "tree_depth")
    op.drop_column("document_chunks", "parent_chunk_id")
