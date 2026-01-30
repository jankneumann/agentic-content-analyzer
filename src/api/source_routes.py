"""Source API Routes.

Provides an overview of all configured ingestion sources and content counts
from the database. Useful for dashboards and monitoring source health.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func

from src.config import settings
from src.config.sources import (
    GmailSource,
    YouTubeChannelSource,
    YouTubePlaylistSource,
)
from src.models.content import Content
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Response Models
# ============================================================================


class SourceInfo(BaseModel):
    """Information about a single configured source."""

    type: str = Field(description="Source type (e.g., rss, youtube_playlist, podcast, gmail)")
    name: str | None = Field(default=None, description="Human-readable source name")
    url: str = Field(description="Source URL or identifier")
    enabled: bool = Field(description="Whether the source is enabled for ingestion")
    tags: list[str] = Field(default_factory=list, description="Tags for categorizing the source")


class SourcesOverview(BaseModel):
    """Overview of all configured sources and content counts."""

    sources: list[SourceInfo] = Field(description="List of all configured sources")
    counts: dict[str, int] = Field(
        description="Content counts by source type (ContentSource enum values)"
    )
    total_sources: int = Field(description="Total number of configured sources")
    enabled_sources: int = Field(description="Number of enabled sources")


router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


# ============================================================================
# Helper Functions
# ============================================================================


def _get_source_url(source) -> str:
    """Extract the URL or identifier from a source object.

    Different source types store their location differently:
    - RSSSource, YouTubeRSSSource, PodcastSource: url field
    - YouTubePlaylistSource: YouTube playlist URL from id
    - YouTubeChannelSource: YouTube channel URL from channel_id
    - GmailSource: Gmail query string
    """
    if isinstance(source, YouTubePlaylistSource):
        return f"https://www.youtube.com/playlist?list={source.id}"
    if isinstance(source, YouTubeChannelSource):
        return f"https://www.youtube.com/channel/{source.channel_id}"
    if isinstance(source, GmailSource):
        return source.query
    # RSSSource, YouTubeRSSSource, PodcastSource all have .url
    return source.url


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=SourcesOverview)
async def list_sources() -> SourcesOverview:
    """
    List all configured sources with content counts.

    Returns an overview of all ingestion sources defined in the sources
    configuration, along with the count of content items ingested per
    source type from the database.
    """
    # Load source configuration
    config = settings.get_sources_config()

    # Build source info list from all configured sources
    source_infos: list[SourceInfo] = []
    for source in config.sources:
        source_infos.append(
            SourceInfo(
                type=source.type,
                name=source.name,
                url=_get_source_url(source),
                enabled=source.enabled,
                tags=source.tags,
            )
        )

    # Get content counts from database grouped by source_type
    with get_db() as db:
        source_counts = (
            db.query(Content.source_type, func.count(Content.id))
            .group_by(Content.source_type)
            .all()
        )
        counts = {source_type.value: count for source_type, count in source_counts}

    total_sources = len(config.sources)
    enabled_sources = sum(1 for s in config.sources if s.enabled)

    return SourcesOverview(
        sources=source_infos,
        counts=counts,
        total_sources=total_sources,
        enabled_sources=enabled_sources,
    )
