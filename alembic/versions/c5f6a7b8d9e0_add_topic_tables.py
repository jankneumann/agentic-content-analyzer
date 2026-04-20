"""add_topic_tables

Revision ID: c5f6a7b8d9e0
Revises: bc56c4b2e94d
Create Date: 2026-04-09 00:00:00.000000

Creates the knowledge base tables: topics, topic_notes, kb_indices.

- topics: persistent compiled knowledge entities with embedding column for
  semantic matching (managed via raw SQL like document_chunks)
- topic_notes: notes attached to topics (observation/question/correction/insight)
- kb_indices: cached markdown indices (master/category/trend/recency)

The embedding column on topics uses pgvector's unconstrained vector type
(actual dimensions determined by the configured embedding provider).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "c5f6a7b8d9e0"
down_revision: Union[str, None] = "bc56c4b2e94d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create topic tables, indexes, and embedding column."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # pgvector should already be enabled by document_chunks migration,
    # but ensure it for safety.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. Create PG enum types only if they don't already exist.
    # Use pg_type catalog check (DO blocks with EXCEPTION handlers can have
    # issues within Alembic's transaction context in some SA versions).
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'topicstatus'")
    )
    if not result.scalar():
        op.execute(
            "CREATE TYPE topicstatus AS ENUM "
            "('draft', 'active', 'stale', 'archived', 'merged')"
        )

    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'topicnotetype'")
    )
    if not result.scalar():
        op.execute(
            "CREATE TYPE topicnotetype AS ENUM "
            "('observation', 'question', 'correction', 'insight')"
        )

    # 2. Create topics table
    if "topics" not in inspector.get_table_names():
        op.create_table(
            "topics",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=500), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "draft",
                    "active",
                    "stale",
                    "archived",
                    "merged",
                    name="topicstatus",
                    create_type=False,
                ),
                nullable=False,
                server_default="draft",
            ),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("article_md", sa.Text(), nullable=True),
            sa.Column("article_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("trend", sa.String(length=50), nullable=True),
            sa.Column(
                "relevance_score", sa.Float(), nullable=False, server_default="0.0"
            ),
            sa.Column(
                "novelty_score", sa.Float(), nullable=False, server_default="0.0"
            ),
            sa.Column(
                "mention_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "source_content_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column(
                "source_summary_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column(
                "source_theme_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column(
                "related_topic_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column("parent_topic_id", sa.Integer(), nullable=True),
            sa.Column("merged_into_id", sa.Integer(), nullable=True),
            sa.Column("last_compiled_at", sa.DateTime(), nullable=True),
            sa.Column("last_evidence_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("compilation_model", sa.String(length=100), nullable=True),
            sa.Column("compilation_token_usage", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_topics_slug"),
            sa.ForeignKeyConstraint(
                ["parent_topic_id"],
                ["topics.id"],
                name="fk_topics_parent_topic_id",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["merged_into_id"],
                ["topics.id"],
                name="fk_topics_merged_into_id",
                ondelete="SET NULL",
            ),
        )

        # Add embedding column via raw SQL (unconstrained vector type)
        op.execute("ALTER TABLE topics ADD COLUMN embedding vector")

    # Indexes
    inspector = Inspector.from_engine(conn)
    if "topics" in inspector.get_table_names():
        existing_indexes = {i["name"] for i in inspector.get_indexes("topics")}

        if "ix_topics_status" not in existing_indexes:
            op.create_index("ix_topics_status", "topics", ["status"])
        if "ix_topics_category" not in existing_indexes:
            op.create_index("ix_topics_category", "topics", ["category"])
        if "ix_topics_trend" not in existing_indexes:
            op.create_index("ix_topics_trend", "topics", ["trend"])
        if "ix_topics_status_relevance" not in existing_indexes:
            op.create_index(
                "ix_topics_status_relevance",
                "topics",
                ["status", "relevance_score"],
            )
        if "ix_topics_last_compiled" not in existing_indexes:
            op.create_index(
                "ix_topics_last_compiled", "topics", ["last_compiled_at"]
            )
        if "ix_topics_created_at" not in existing_indexes:
            op.create_index("ix_topics_created_at", "topics", ["created_at"])

    # 3. Create topic_notes table
    inspector = Inspector.from_engine(conn)
    if "topic_notes" not in inspector.get_table_names():
        op.create_table(
            "topic_notes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("topic_id", sa.Integer(), nullable=False),
            sa.Column(
                "note_type",
                postgresql.ENUM(
                    "observation",
                    "question",
                    "correction",
                    "insight",
                    name="topicnotetype",
                    create_type=False,
                ),
                nullable=False,
                server_default="observation",
            ),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "author", sa.String(length=255), nullable=False, server_default="system"
            ),
            sa.Column(
                "filed_back", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["topic_id"],
                ["topics.id"],
                name="fk_topic_notes_topic_id",
                ondelete="CASCADE",
            ),
        )

        op.create_index("ix_topic_notes_topic_id", "topic_notes", ["topic_id"])
        op.create_index("ix_topic_notes_created_at", "topic_notes", ["created_at"])

    # 4. Create kb_indices table
    inspector = Inspector.from_engine(conn)
    if "kb_indices" not in inspector.get_table_names():
        op.create_table(
            "kb_indices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("index_type", sa.String(length=100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "generated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("index_type", name="uq_kb_indices_index_type"),
        )

    # 5. Create HNSW index on topics.embedding for semantic matching
    op.execute(
        """
        DO $$
        BEGIN
            -- Only create HNSW index if pgvector supports it (v0.5+)
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                BEGIN
                    CREATE INDEX IF NOT EXISTS ix_topics_embedding_hnsw
                    ON topics USING hnsw (embedding vector_cosine_ops);
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Skipping topics HNSW index: %', SQLERRM;
                END;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    """Drop topic tables, indexes, and enum types."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Drop kb_indices first (no dependencies)
    if "kb_indices" in inspector.get_table_names():
        op.drop_table("kb_indices")

    # Drop topic_notes (depends on topics)
    if "topic_notes" in inspector.get_table_names():
        op.drop_index("ix_topic_notes_created_at", table_name="topic_notes")
        op.drop_index("ix_topic_notes_topic_id", table_name="topic_notes")
        op.drop_table("topic_notes")

    # Drop topics table and its indexes
    if "topics" in inspector.get_table_names():
        op.execute("DROP INDEX IF EXISTS ix_topics_embedding_hnsw")

        for idx in (
            "ix_topics_created_at",
            "ix_topics_last_compiled",
            "ix_topics_status_relevance",
            "ix_topics_trend",
            "ix_topics_category",
            "ix_topics_status",
        ):
            try:
                op.drop_index(idx, table_name="topics")
            except Exception:  # noqa: BLE001
                pass

        op.drop_table("topics")

    # Drop enum types
    sa.Enum(name="topicnotetype").drop(conn, checkfirst=True)
    sa.Enum(name="topicstatus").drop(conn, checkfirst=True)
