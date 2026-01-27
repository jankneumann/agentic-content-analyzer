"""Chat data models for AI revision conversations."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.base import Base


class ArtifactType(str, Enum):
    """Type of artifact the conversation is about."""

    SUMMARY = "summary"
    DIGEST = "digest"
    SCRIPT = "script"


class MessageRole(str, Enum):
    """Role of message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    """Conversation database model.

    A chat session tied to a specific artifact for revision.
    """

    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)  # UUID
    artifact_type = Column(String(20), nullable=False)  # summary, digest, script
    artifact_id = Column(Integer, nullable=False)  # ID of the related artifact
    title = Column(String(255), nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_conversations_artifact", "artifact_type", "artifact_id"),
        Index("ix_conversations_updated_at", "updated_at"),
    )


class ChatMessage(Base):
    """Chat message database model.

    Individual message in a conversation.
    """

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True)  # UUID
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Metadata (for assistant messages)
    model_used = Column(String(100), nullable=True)
    token_usage = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    web_search_used = Column(Boolean, default=False)
    web_search_queries = Column(JSON, nullable=True)  # List[str]

    # Suggested actions (JSON array of action objects)
    suggested_actions = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index(
            "ix_chat_messages_conversation_id_created_at",
            "conversation_id",
            "created_at",
        ),
    )
