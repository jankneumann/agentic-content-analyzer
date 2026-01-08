"""Data models for the Newsletter Aggregator."""

from src.models.chat import ArtifactType, ChatMessage, Conversation, MessageRole
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.newsletter import Base, Newsletter, ProcessingStatus
from src.models.podcast import Podcast, PodcastLength, PodcastScriptRecord, PodcastStatus
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.models.summary import NewsletterSummary, SummaryData
from src.models.theme import ThemeAnalysis

__all__ = [
    # Base
    "Base",
    # Newsletter
    "Newsletter",
    "ProcessingStatus",
    # Summary
    "NewsletterSummary",
    "SummaryData",
    # Digest
    "Digest",
    "DigestType",
    "DigestStatus",
    # Podcast
    "PodcastScriptRecord",
    "Podcast",
    "PodcastStatus",
    "PodcastLength",
    # Theme
    "ThemeAnalysis",
    # Chat
    "Conversation",
    "ChatMessage",
    "ArtifactType",
    "MessageRole",
    # Revision
    "RevisionContext",
    "RevisionResult",
    "RevisionTurn",
]
