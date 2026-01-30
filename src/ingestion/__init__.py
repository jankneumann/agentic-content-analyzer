"""Content ingestion modules.

This module provides ingestion services for various content sources
using the unified Content model.
"""

from src.ingestion.gmail import (
    GmailClient,
    GmailContentIngestionService,
)
from src.ingestion.podcast import (
    PodcastClient,
    PodcastContentIngestionService,
)
from src.ingestion.rss import (
    RSSClient,
    RSSContentIngestionService,
)
from src.ingestion.youtube import (
    YouTubeClient,
    YouTubeContentIngestionService,
)

__all__ = [
    # Gmail
    "GmailClient",
    "GmailContentIngestionService",
    # Podcast
    "PodcastClient",
    "PodcastContentIngestionService",
    # RSS
    "RSSClient",
    "RSSContentIngestionService",
    # YouTube
    "YouTubeClient",
    "YouTubeContentIngestionService",
]
