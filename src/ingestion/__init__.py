"""Content ingestion modules.

This module provides ingestion services for various content sources.
Use the *ContentIngestionService classes for the unified Content model.

.. deprecated::
    The legacy *IngestionService classes (GmailIngestionService, RSSIngestionService)
    are deprecated. Use *ContentIngestionService classes instead.
"""

from src.ingestion.gmail import (
    GmailClient,
    GmailContentIngestionService,
    GmailIngestionService,  # Deprecated
)
from src.ingestion.rss import (
    RSSClient,
    RSSContentIngestionService,
    RSSIngestionService,  # Deprecated
)

__all__ = [
    # Gmail
    "GmailClient",
    "GmailContentIngestionService",  # Preferred
    "GmailIngestionService",  # Deprecated - use GmailContentIngestionService
    # RSS
    "RSSClient",
    "RSSContentIngestionService",  # Preferred
    "RSSIngestionService",  # Deprecated - use RSSContentIngestionService
]
