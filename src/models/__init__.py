"""Data models for the Newsletter Aggregator."""

from src.models.chat import ArtifactType, ChatMessage, Conversation, MessageRole
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata, TableData
from src.models.newsletter import Base, Newsletter, NewsletterSource, ProcessingStatus
from src.models.podcast import Podcast, PodcastLength, PodcastScriptRecord, PodcastStatus
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.models.settings import PromptOverride
from src.models.summary import NewsletterSummary, SummaryData
from src.models.theme import ThemeAnalysis
from src.models.youtube import (
    TimestampedQuote,
    TranscriptSegment,
    YouTubeTranscript,
    format_timestamp,
    parse_timestamp,
)

__all__ = [
    # Base
    "Base",
    # Newsletter
    "Newsletter",
    "NewsletterSource",
    "ProcessingStatus",
    # Document
    "DocumentContent",
    "DocumentFormat",
    "DocumentMetadata",
    "TableData",
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
    # Settings
    "PromptOverride",
    # YouTube
    "YouTubeTranscript",
    "TranscriptSegment",
    "TimestampedQuote",
    "format_timestamp",
    "parse_timestamp",
]
