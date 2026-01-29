"""Bolt performance chat indexes

Revision ID: b017a1a2b3c4
Revises: e4f5a6b7c8d9, e1f2a3b4c5d6
Create Date: 2026-01-25 10:00:00.000000

"""
from collections.abc import Sequence

from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b017a1a2b3c4'
down_revision: str | Sequence[str] | None = ('e4f5a6b7c8d9', 'e1f2a3b4c5d6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # helper to check index existence
    def index_exists(table_name, index_name):
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)

    # ix_conversations_artifact
    if not index_exists('conversations', 'ix_conversations_artifact'):
        op.create_index(
            'ix_conversations_artifact',
            'conversations',
            ['artifact_type', 'artifact_id'],
            unique=False
        )

    # ix_conversations_updated_at
    if not index_exists('conversations', 'ix_conversations_updated_at'):
        op.create_index(
            'ix_conversations_updated_at',
            'conversations',
            ['updated_at'],
            unique=False
        )

    # ix_chat_messages_conversation_id_created_at
    if not index_exists('chat_messages', 'ix_chat_messages_conversation_id_created_at'):
        op.create_index(
            'ix_chat_messages_conversation_id_created_at',
            'chat_messages',
            ['conversation_id', 'created_at'],
            unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    def index_exists(table_name, index_name):
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)

    # Drop ix_chat_messages_conversation_id_created_at
    if index_exists('chat_messages', 'ix_chat_messages_conversation_id_created_at'):
        op.drop_index('ix_chat_messages_conversation_id_created_at', table_name='chat_messages')

    # Drop ix_conversations_updated_at
    if index_exists('conversations', 'ix_conversations_updated_at'):
        op.drop_index('ix_conversations_updated_at', table_name='conversations')

    # Drop ix_conversations_artifact
    if index_exists('conversations', 'ix_conversations_artifact'):
        op.drop_index('ix_conversations_artifact', table_name='conversations')
