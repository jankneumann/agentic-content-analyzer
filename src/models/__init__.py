"""Data models for the Newsletter Aggregator.

The Content model provides unified handling for all source types (Gmail, RSS,
YouTube, file uploads) with markdown-first storage optimized for LLM consumption.
"""

from src.models.agent_insight import AgentInsight, InsightType
from src.models.agent_memory import AgentMemory, MemoryType
from src.models.agent_task import AgentTask, AgentTaskSource, AgentTaskStatus
from src.models.approval_request import ApprovalRequest, ApprovalStatus, RiskLevel
from src.models.audio_digest import (
    AudioDigest,
    AudioDigestCreate,
    AudioDigestListItem,
    AudioDigestResponse,
    AudioDigestStatus,
)
from src.models.base import Base
from src.models.chat import ArtifactType, ChatMessage, Conversation, MessageRole
from src.models.chunk import ChunkType, DocumentChunk
from src.models.content import Content, ContentSource, ContentStatus
from src.models.content_reference import (
    ContentReference,
    ExternalIdType,
    ReferenceListResponse,
    ReferenceResponse,
    ReferenceType,
    ResolutionStatus,
)
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata, TableData
from src.models.evaluation import (
    DatasetStatus,
    EvaluationConsensus,
    EvaluationDataset,
    EvaluationResult,
    EvaluationSample,
    JudgeType,
    Preference,
    RoutingConfig,
    RoutingDecision,
    RoutingMode,
)
from src.models.image import Image, ImageSource
from src.models.notification import DeviceRegistration, NotificationEvent, NotificationEventType
from src.models.podcast import Podcast, PodcastLength, PodcastScriptRecord, PodcastStatus
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.models.search import (
    ChunkResult,
    SearchFilter,
    SearchMeta,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchScores,
    SearchType,
)
from src.models.settings import PromptOverride
from src.models.summary import NewsletterSummary, Summary, SummaryData
from src.models.theme import ThemeAnalysis
from src.models.topic import KBIndex, Topic, TopicNote, TopicNoteType, TopicStatus
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
    # Chunk
    "DocumentChunk",
    "ChunkType",
    # Search
    "SearchType",
    "SearchQuery",
    "SearchFilter",
    "ChunkResult",
    "SearchScores",
    "SearchResult",
    "SearchMeta",
    "SearchResponse",
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
    # Content Reference
    "ContentReference",
    "ReferenceType",
    "ExternalIdType",
    "ResolutionStatus",
    "ReferenceResponse",
    "ReferenceListResponse",
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
    # Knowledge Base
    "Topic",
    "TopicNote",
    "TopicStatus",
    "TopicNoteType",
    "KBIndex",
    # Chat
    "Conversation",
    "ChatMessage",
    "ArtifactType",
    "MessageRole",
    # Revision
    "RevisionContext",
    "RevisionResult",
    "RevisionTurn",
    # Notification
    "NotificationEvent",
    "NotificationEventType",
    "DeviceRegistration",
    # Agent Models
    "AgentTask",
    "AgentTaskStatus",
    "AgentTaskSource",
    "AgentInsight",
    "InsightType",
    "AgentMemory",
    "MemoryType",
    "ApprovalRequest",
    "ApprovalStatus",
    "RiskLevel",
    # Evaluation / Routing
    "RoutingConfig",
    "RoutingMode",
    "EvaluationDataset",
    "EvaluationSample",
    "EvaluationResult",
    "EvaluationConsensus",
    "RoutingDecision",
    "DatasetStatus",
    "JudgeType",
    "Preference",
    # Settings
    "PromptOverride",
    # YouTube
    "YouTubeTranscript",
    "TranscriptSegment",
    "TimestampedQuote",
    "format_timestamp",
    "parse_timestamp",
]
