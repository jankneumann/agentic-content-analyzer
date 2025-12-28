"""Newsletter ingestion modules."""

from src.ingestion.gmail import GmailClient, GmailIngestionService
from src.ingestion.substack import SubstackRSSClient, SubstackIngestionService

__all__ = [
    "GmailClient",
    "GmailIngestionService",
    "SubstackRSSClient",
    "SubstackIngestionService",
]
