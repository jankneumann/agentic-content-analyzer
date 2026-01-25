"""Data models for the Newsletter Aggregator.

The Content model provides unified handling for all source types (Gmail, RSS,
YouTube, file uploads) with markdown-first storage optimized for LLM consumption.
"""

from src.models.audio_digest import (
    AudioDigest,
    AudioDigestCreate,
    AudioDigestListItem,
    AudioDigestResponse,
    AudioDigestStatus,
)
from src.models.base import Base
from src.models.chat import ArtifactType, ChatMessage, Conversation, MessageRole
from src.models.content import Content, ContentSource, ContentStatus
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata, TableData
from src.models.image import Image, ImageSource
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
    # Audio Digest
    "AudioDigest",
    "AudioDigestCreate",
    "AudioDigestListItem",
    "AudioDigestResponse",
    "AudioDigestStatus",
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
