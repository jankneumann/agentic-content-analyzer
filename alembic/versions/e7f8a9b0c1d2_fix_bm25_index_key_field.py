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
unnoticed. This migration drops the broken index and recreates it correctly.
Provider denial of the optional extension is handled as an unavailable
capability, while index syntax errors remain loud once pg_search is installed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "b7a1c9d5e2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_pg_search_installed(conn: Connection) -> bool:
    """Install optional pg_search when permitted without aborting the migration."""

    installed = conn.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_search'")
    ).scalar()
    if installed:
        return True
    try:
        with conn.begin_nested():
            conn.execute(sa.text("CREATE EXTENSION pg_search"))
    except sa.exc.DBAPIError:
        return False
    return True


def upgrade() -> None:
    """Drop broken BM25 index and recreate with id in column list."""
    conn = op.get_bind()
    # Drop the index unconditionally — IF EXISTS is safe whether it was
    # created (in production, malformed) or never existed (fresh deploys
    # where pg_search wasn't available).
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_bm25")

    # Provider catalogs may advertise deprecated extensions that users cannot
    # install. Probe installation in a savepoint, but keep index syntax errors
    # loud once pg_search is genuinely available.
    if _ensure_pg_search_installed(conn):
        op.execute(
            """
            CREATE INDEX ix_document_chunks_bm25
            ON document_chunks
            USING bm25 (id, chunk_text)
            WITH (key_field='id')
            """
        )


def downgrade() -> None:
    """Restore the original (broken) index for parity with prior revision."""
    conn = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_bm25")
    if _ensure_pg_search_installed(conn):
        op.execute(
            """
            CREATE INDEX ix_document_chunks_bm25
            ON document_chunks USING bm25 (chunk_text) WITH (key_field='id')
            """
        )
