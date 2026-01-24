"""Data models for the Newsletter Aggregator.

.. note::
    The Newsletter model is deprecated. Use :class:`Content` instead for all new code.
    The Content model provides unified handling for all source types (Gmail, RSS,
    YouTube, file uploads) with markdown-first storage optimized for LLM consumption.

    See: openspec/changes/deprecate-newsletter-model/ for migration guide.
"""

from src.models.base import Base
from src.models.chat import ArtifactType, ChatMessage, Conversation, MessageRole
from src.models.content import Content, ContentSource, ContentStatus
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata, TableData
from src.models.image import Image, ImageSource

# Legacy Newsletter imports - deprecated, will be removed
# These are kept temporarily for backwards compatibility during migration
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.models.podcast import Podcast, PodcastLength, PodcastScriptRecord, PodcastStatus
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.models.settings import PromptOverride
from src.models.summary import NewsletterSummary, Summary, SummaryData
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
    # Newsletter (deprecated - use Content)
    "Newsletter",
    "NewsletterSource",
    "ProcessingStatus",
    # Content (unified model)
    "Content",
    "ContentSource",
    "ContentStatus",
    # Document
    "DocumentContent",
    "DocumentFormat",
    "DocumentMetadata",
    "TableData",
    # Image
    "Image",
    "ImageSource",
    # Summary
    "Summary",
    "NewsletterSummary",  # Deprecated alias for Summary
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
