"""Newsletter ingestion modules."""

from src.ingestion.gmail import GmailClient, GmailIngestionService
from src.ingestion.rss import RSSClient, RSSIngestionService

__all__ = [
    "GmailClient",
    "GmailIngestionService",
    "RSSClient",
    "RSSIngestionService",
]
