"""add_document_chunks_table

Revision ID: b2c3d4e5f6a7
Revises: f9a8b7c6d5e5
Create Date: 2026-02-10 12:00:00.000000

This migration creates the document_chunks table for full-text and semantic
search over ingested content. It includes:
- pgvector extension for embedding storage
- HNSW index for approximate nearest neighbor search
- GIN index on TSVECTOR column for full-text search
- TSVECTOR auto-update trigger on chunk_text
- Conditional BM25 index if pg_search extension is available
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "f9a8b7c6d5e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_chunks table with vector and full-text search support."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create document_chunks table (if not exists)
    if "document_chunks" not in inspector.get_table_names():
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("content_id", sa.Integer(), nullable=False),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("section_path", sa.String(length=500), nullable=True),
            sa.Column("heading_text", sa.String(length=500), nullable=True),
            sa.Column("chunk_type", sa.String(length=50), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("start_char", sa.Integer(), nullable=True),
            sa.Column("end_char", sa.Integer(), nullable=True),
            sa.Column("timestamp_start", sa.Float(), nullable=True),
            sa.Column("timestamp_end", sa.Float(), nullable=True),
            sa.Column("deep_link_url", sa.String(length=2000), nullable=True),
            # embedding and search_vector columns added via raw SQL below
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["content_id"],
                ["contents.id"],
                name="fk_document_chunks_content_id",
                ondelete="CASCADE",
            ),
        )

        # Add the embedding column using pgvector's vector type (384 dimensions default)
        op.execute(
            "ALTER TABLE document_chunks ADD COLUMN embedding vector(384)"
        )

        # Add the search_vector TSVECTOR column
        op.execute(
            "ALTER TABLE document_chunks ADD COLUMN search_vector tsvector"
        )

    # 3. Create indexes
    # Re-fetch inspector after table creation
    inspector = Inspector.from_engine(conn)
    if "document_chunks" in inspector.get_table_names():
        indexes = inspector.get_indexes("document_chunks")
        index_names = [i["name"] for i in indexes]

        # Standard B-tree index on content_id
        if "ix_document_chunks_content_id" not in index_names:
            op.create_index(
                "ix_document_chunks_content_id",
                "document_chunks",
                ["content_id"],
            )

        # Standard B-tree index on chunk_type
        if "ix_document_chunks_chunk_type" not in index_names:
            op.create_index(
                "ix_document_chunks_chunk_type",
                "document_chunks",
                ["chunk_type"],
            )

        # HNSW index on embedding column for approximate nearest neighbor search
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """)

        # GIN index on search_vector for full-text search
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_document_chunks_search_vector_gin
            ON document_chunks USING gin (search_vector)
        """)

    # 4. Create TSVECTOR trigger function and trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS document_chunks_search_vector_trigger
            ON document_chunks
    """)

    op.execute("""
        CREATE TRIGGER document_chunks_search_vector_trigger
            BEFORE INSERT OR UPDATE OF chunk_text
            ON document_chunks
            FOR EACH ROW
            EXECUTE FUNCTION document_chunks_search_vector_update()
    """)

    # 5. Conditionally create BM25 index if pg_search extension is available
    # Wrapped in EXCEPTION handler because pg_search syntax varies across providers
    # (e.g., Neon's pg_search version may not support the same WITH options)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_search') THEN
                CREATE INDEX IF NOT EXISTS ix_document_chunks_bm25
                ON document_chunks USING bm25 (chunk_text) WITH (key_field='id');
            END IF;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'BM25 index creation skipped: %', SQLERRM;
        END $$
    """)


def downgrade() -> None:
    """Drop document_chunks table and associated objects."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Drop trigger first (depends on table and function)
    op.execute("""
        DROP TRIGGER IF EXISTS document_chunks_search_vector_trigger
            ON document_chunks
    """)

    # Drop trigger function
    op.execute(
        "DROP FUNCTION IF EXISTS document_chunks_search_vector_update()"
    )

    # Drop indexes and table (only if table exists)
    if "document_chunks" in inspector.get_table_names():
        # Drop BM25 index (conditional — may not exist)
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_bm25")

        # Drop GIN index on search_vector
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector_gin")

        # Drop HNSW index on embedding
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")

        # Drop standard indexes
        indexes = inspector.get_indexes("document_chunks")
        index_names = [i["name"] for i in indexes]

        if "ix_document_chunks_chunk_type" in index_names:
            op.drop_index(
                "ix_document_chunks_chunk_type",
                table_name="document_chunks",
            )

        if "ix_document_chunks_content_id" in index_names:
            op.drop_index(
                "ix_document_chunks_content_id",
                table_name="document_chunks",
            )

        # Drop table
        op.drop_table("document_chunks")

    # Note: We do NOT drop the pgvector extension here because other tables
    # may depend on it.
