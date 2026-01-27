"""Tests for Chat data models."""

from src.models.chat import ChatMessage, Conversation


class TestChatModel:
    """Tests for Chat SQLAlchemy models."""

    def test_conversation_indexes(self):
        """Test that Conversation model has expected indexes."""
        # Get all index names
        indexes = {idx.name for idx in Conversation.__table__.indexes}
        assert "ix_conversations_artifact" in indexes
        assert "ix_conversations_updated_at" in indexes

    def test_chat_message_indexes(self):
        """Test that ChatMessage model has expected indexes."""
        indexes = {idx.name for idx in ChatMessage.__table__.indexes}
        assert "ix_chat_messages_conversation_id_created_at" in indexes
