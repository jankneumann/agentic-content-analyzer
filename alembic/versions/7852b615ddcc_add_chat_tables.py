"""add_chat_tables

Revision ID: 7852b615ddcc
Revises: a1b2c3d4e5f6
Create Date: 2026-01-07 22:53:00.523024

Adds conversations and chat_messages tables for AI revision chatbot feature.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7852b615ddcc"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create conversations and chat_messages tables."""

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), nullable=False),  # UUID
        sa.Column("artifact_type", sa.String(20), nullable=False),  # summary, digest, script
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_artifact", "conversations", ["artifact_type", "artifact_id"])
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), nullable=False),  # UUID
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user, assistant, system
        sa.Column("content", sa.Text(), nullable=False),
        # Metadata for assistant messages
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("web_search_used", sa.Boolean(), server_default="false"),
        sa.Column("web_search_queries", sa.JSON(), nullable=True),
        # Suggested actions (JSON array of action objects)
        sa.Column("suggested_actions", sa.JSON(), nullable=True),
        # Timestamp
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    """Drop chat_messages and conversations tables."""

    # Drop chat_messages table first (has FK to conversations)
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    # Drop conversations table
    op.drop_index("ix_conversations_updated_at", table_name="conversations")
    op.drop_index("ix_conversations_artifact", table_name="conversations")
    op.drop_table("conversations")
