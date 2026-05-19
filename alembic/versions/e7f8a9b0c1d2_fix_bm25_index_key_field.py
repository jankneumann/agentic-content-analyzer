"""fix_bm25_index_key_field

Revision ID: e7f8a9b0c1d2
Revises: b7a1c9d5e2f0
Create Date: 2026-05-18 21:50:00.000000

Fixes the pg_search BM25 index on document_chunks so INSERTs no longer fail
with "No key field defined". The original migration b2c3d4e5f6a7 used legacy
pg_search syntax that referenced key_field='id' without including id in the
indexed column list. Current pg_search (v0.13+) requires the key_field to be
the first column in the index column list — otherwise the index is malformed
and every INSERT raises psycopg2.errors.InternalError_: No key field defined.

The original migration's CREATE INDEX is wrapped in DO ... EXCEPTION WHEN
OTHERS, which silently swallowed the underlying issue, so this bug shipped
unnoticed. This migration drops the broken index and recreates it correctly;
it intentionally does NOT swallow exceptions so future schema drift is loud.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "b7a1c9d5e2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop broken BM25 index and recreate with id in column list."""
    # Drop the index unconditionally — IF EXISTS is safe whether it was
    # created (in production, malformed) or never existed (fresh deploys
    # where pg_search wasn't available).
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_bm25")

    # Recreate with the fixed column list. Same availability guard as the
    # original migration, but errors are RAISEd not swallowed so any future
    # syntax drift surfaces immediately.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_search') THEN
                CREATE EXTENSION IF NOT EXISTS pg_search;
                CREATE INDEX ix_document_chunks_bm25
                ON document_chunks
                USING bm25 (id, chunk_text)
                WITH (key_field='id');
                RAISE NOTICE 'BM25 index recreated with id as key_field';
            ELSE
                RAISE NOTICE 'pg_search extension not available — BM25 index skipped';
            END IF;
        END $$
    """)


def downgrade() -> None:
    """Restore the original (broken) index for parity with prior revision."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_bm25")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_search') THEN
                CREATE EXTENSION IF NOT EXISTS pg_search;
                CREATE INDEX ix_document_chunks_bm25
                ON document_chunks USING bm25 (chunk_text) WITH (key_field='id');
            END IF;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'BM25 index creation skipped: %', SQLERRM;
        END $$
    """)
