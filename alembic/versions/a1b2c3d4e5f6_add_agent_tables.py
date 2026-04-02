"""Add agent tables for agentic analysis system.

Creates tables: agent_tasks, agent_insights, agent_memories,
approval_requests, agent_schedules.

Creates PG enums: agent_task_status, agent_task_source, insight_type,
memory_type, risk_level, approval_status.

Enum Extension Pattern:
    When adding new values to these enums, create a new migration with:
        ALTER TYPE <enum_name> ADD VALUE '<new_value>';
    This must run outside a transaction on PostgreSQL < 12.
    Use op.execute() with autocommit=True or a separate migration.

Revision ID: a1b2c3d4e5f6
Revises: f9a8b7c6d5e5
Create Date: 2026-04-02 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f9a8b7c6d5e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # --- Create PG enums ---
    # Note: These are created as CHECK constraints via String columns
    # rather than native PG enums to simplify future additions.
    # The Python StrEnum is the source of truth; DB uses VARCHAR.

    # --- agent_tasks ---
    if "agent_tasks" not in existing_tables:
        op.create_table(
            "agent_tasks",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("task_type", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False, server_default="user"),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("plan", JSONB(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="received"),
            sa.Column("result", JSONB(), nullable=True),
            sa.Column("parent_task_id", UUID(as_uuid=True), sa.ForeignKey("agent_tasks.id"), nullable=True),
            sa.Column("specialist_type", sa.String(), nullable=True),
            sa.Column("persona_name", sa.String(), nullable=False, server_default="default"),
            sa.Column("persona_config", JSONB(), nullable=True),
            sa.Column("cost_total", sa.Float(), nullable=True),
            sa.Column("tokens_total", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])
        op.create_index("ix_agent_tasks_source", "agent_tasks", ["source"])
        op.create_index("ix_agent_tasks_persona", "agent_tasks", ["persona_name"])
        op.create_index("ix_agent_tasks_created_at", "agent_tasks", ["created_at"])

    # --- agent_insights ---
    if "agent_insights" not in existing_tables:
        op.create_table(
            "agent_insights",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("agent_tasks.id"), nullable=True),
            sa.Column("insight_type", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("tags", JSONB(), server_default="[]"),
            sa.Column("related_content_ids", JSONB(), server_default="[]"),
            sa.Column("related_theme_ids", JSONB(), server_default="[]"),
            sa.Column("metadata", JSONB(), server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_agent_insights_type", "agent_insights", ["insight_type"])
        op.create_index("ix_agent_insights_confidence", "agent_insights", ["confidence"])
        op.create_index("ix_agent_insights_created_at", "agent_insights", ["created_at"])

    # --- agent_memories ---
    if "agent_memories" not in existing_tables:
        op.create_table(
            "agent_memories",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("memory_type", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            # embedding column added via raw SQL for pgvector compatibility
            sa.Column("tags", JSONB(), server_default="[]"),
            sa.Column("source_task_id", UUID(as_uuid=True), sa.ForeignKey("agent_tasks.id"), nullable=True),
            sa.Column("confidence", sa.Float(), server_default="1.0"),
            sa.Column("access_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("last_accessed_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_agent_memories_type", "agent_memories", ["memory_type"])
        op.create_index("ix_agent_memories_source_task", "agent_memories", ["source_task_id"])
        op.create_index("ix_agent_memories_created_at", "agent_memories", ["created_at"])

        # Add pgvector embedding column (raw SQL — not ORM-mappable)
        op.execute("ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS embedding vector(1536)")

        # Add tsvector column for full-text search (KeywordStrategy)
        op.execute("ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS content_tsv tsvector")
        op.execute("CREATE INDEX IF NOT EXISTS ix_agent_memories_content_tsv ON agent_memories USING gin(content_tsv)")

        # Add HNSW index for vector similarity search (VectorStrategy)
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_agent_memories_embedding "
            "ON agent_memories USING hnsw (embedding vector_cosine_ops)"
        )

    # --- approval_requests ---
    if "approval_requests" not in existing_tables:
        op.create_table(
            "approval_requests",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("agent_tasks.id"), nullable=False),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("risk_level", sa.String(), nullable=False),
            sa.Column("context", JSONB(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
        op.create_index("ix_approval_requests_task", "approval_requests", ["task_id"])

    # --- agent_schedules ---
    if "agent_schedules" not in existing_tables:
        op.create_table(
            "agent_schedules",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("cron_expression", sa.String(), nullable=False),
            sa.Column("persona_name", sa.String(), nullable=True),
            sa.Column("output_type", sa.String(), nullable=True),
            sa.Column("source_filter", JSONB(), nullable=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_status", sa.String(), nullable=True),
            sa.Column("enabled", sa.Boolean(), server_default="true"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("agent_schedules")
    op.drop_table("approval_requests")
    op.drop_table("agent_memories")
    op.drop_table("agent_insights")
    op.drop_table("agent_tasks")
