"""Add embedding provider/model metadata columns and unconstrain vector.

Adds:
- embedding_provider (VARCHAR 50): which provider generated the embedding
- embedding_model (VARCHAR 100): which model generated the embedding
- Composite index on (embedding_provider, embedding_model)
- Unconstrains embedding column from vector(384) to vector
- Backfills existing embeddings with provider='unknown', model='unknown'

Revision ID: a1b2c3d4e5f7
Revises: 1a4ad3270eb7
Create Date: 2026-02-15
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = '1a4ad3270eb7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add embedding_provider column
    op.add_column(
        'document_chunks',
        sa.Column('embedding_provider', sa.String(50), nullable=True),
    )

    # Add embedding_model column
    op.add_column(
        'document_chunks',
        sa.Column('embedding_model', sa.String(100), nullable=True),
    )

    # Create composite index on metadata columns
    op.create_index(
        'ix_document_chunks_embedding_meta',
        'document_chunks',
        ['embedding_provider', 'embedding_model'],
    )

    # Unconstrain vector column from vector(384) to vector
    # This is safe: pgvector accepts unconstrained vector type, existing data
    # is preserved via the USING clause. HNSW indexes still work.
    op.execute("""
        DO $$
        BEGIN
            -- Only alter if the column exists and has a constrained type
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_chunks' AND column_name = 'embedding'
            ) THEN
                ALTER TABLE document_chunks
                    ALTER COLUMN embedding TYPE vector USING embedding::vector;
            END IF;
        END $$;
    """)

    # Backfill existing rows that have embeddings with 'unknown' metadata
    op.execute("""
        UPDATE document_chunks
        SET embedding_provider = 'unknown', embedding_model = 'unknown'
        WHERE embedding IS NOT NULL
          AND embedding_provider IS NULL
    """)


def downgrade() -> None:
    # Remove the composite index
    op.drop_index('ix_document_chunks_embedding_meta', table_name='document_chunks')

    # Remove metadata columns
    op.drop_column('document_chunks', 'embedding_model')
    op.drop_column('document_chunks', 'embedding_provider')

    # Note: We do NOT re-constrain the vector column to vector(384) on
    # downgrade because existing data may have different dimensions.
    # Manually ALTER TABLE if needed after downgrade.
