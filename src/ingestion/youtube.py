"""YouTube transcript ingestion.

Provides Content model ingestion for YouTube videos using the unified content model.
Creates Content records with markdown-formatted transcripts including timestamp links.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from src.config import settings
from src.models.content import Content, ContentSource, ContentStatus
from src.models.youtube import TranscriptSegment, YouTubeTranscript
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.config.sources import YouTubeChannelSource, YouTubePlaylistSource, YouTubeRSSSource

logger = get_logger(__name__)

# YouTube API scopes (for private playlists)
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# Default language preferences for transcripts
DEFAULT_LANGUAGES = ["en", "en-US", "en-GB"]


class YouTubeClient:
    """YouTube API client for fetching playlist videos and transcripts."""

    def __init__(self, use_oauth: bool = True) -> None:
        """
        Initialize YouTube client.

        Args:
            use_oauth: If True, attempt OAuth for private playlist access.
                      Falls back to API key if OAuth credentials are unavailable or expired.
        """
        self._service: Any = None
        self.use_oauth = use_oauth
        self.oauth_available: bool = False
        self._authenticated: bool = False

    def _ensure_service(self) -> Any:
        """Lazily authenticate and return the YouTube Data API service.

        Authentication is deferred until a method actually needs the Data API
        (e.g. get_playlist_videos, resolve_channel_to_playlist). This allows
        transcript-only usage (get_transcript) without requiring any API credentials.

        Returns:
            Authenticated YouTube Data API service object.

        Raises:
            ValueError: If no API key or OAuth credentials are available.
        """
        if not self._authenticated:
            self._authenticate()
            self._authenticated = True
        return self._service

    @property
    def service(self) -> Any:
        """YouTube Data API service (lazy-authenticated on first access)."""
        return self._ensure_service()

    @service.setter
    def service(self, value: Any) -> None:
        """Allow setting service directly (used in tests)."""
        self._service = value
        self._authenticated = True

    def _authenticate(self) -> None:
        """Authenticate with YouTube API, falling back to API key if OAuth fails."""
        if self.use_oauth:
            try:
                self._authenticate_oauth()
                self.oauth_available = True
                return
            except (RefreshError, FileNotFoundError) as e:
                logger.warning(
                    f"OAuth authentication failed ({type(e).__name__}), "
                    "falling back to API key. Private playlists will be skipped."
                )
        self._authenticate_api_key()

    def _authenticate_oauth(self) -> None:
        """Authenticate using OAuth2 (for private playlists)."""
        creds = None

        # Load existing credentials
        if os.path.exists(settings.youtube_token_file):
            creds = Credentials.from_authorized_user_file(settings.youtube_token_file, SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing YouTube credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(settings.youtube_credentials_file):
                    raise FileNotFoundError(
                        f"YouTube credentials file not found: {settings.youtube_credentials_file}"
                    )
                logger.info("Starting YouTube OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.youtube_credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(settings.youtube_token_file, "w") as token:
                token.write(creds.to_json())
            logger.info("YouTube credentials saved")

        self._service = build("youtube", "v3", credentials=creds)
        logger.info("YouTube API client initialized (OAuth)")

    def _authenticate_api_key(self) -> None:
        """Authenticate using API key (for public playlists only)."""
        api_key = settings.get_youtube_api_key()
        if not api_key:
            raise ValueError(
                "YOUTUBE_API_KEY or GOOGLE_API_KEY required for public playlist access"
            )

        self._service = build("youtube", "v3", developerKey=api_key)
        logger.info("YouTube API client initialized (API key)")

    # In-memory cache for channel_id → uploads playlist ID
    _channel_playlist_cache: ClassVar[dict[str, str]] = {}

    def resolve_channel_to_playlist(self, channel_id: str) -> str | None:
        """Resolve a YouTube channel ID to its uploads playlist ID.

        Uses the YouTube Data API channels().list(part="contentDetails") to look
        up the channel's "uploads" playlist, which contains all public videos.

        Results are cached in-memory to avoid repeated API calls for the same
        channel across multiple ingestion runs within a single process.

        Args:
            channel_id: YouTube channel ID (e.g. "UCxxxxxx")

        Returns:
            Uploads playlist ID (e.g. "UUxxxxxx") or None if not found.
        """
        # Check cache first
        if channel_id in self._channel_playlist_cache:
            cached = self._channel_playlist_cache[channel_id]
            logger.debug(f"Channel {channel_id} → playlist {cached} (cached)")
            return cached

        try:
            request = self.service.channels().list(
                part="contentDetails",
                id=channel_id,
            )
            response = request.execute()

            items = response.get("items", [])
            if not items:
                logger.warning(f"Channel not found: {channel_id}")
                return None

            related = items[0]["contentDetails"]["relatedPlaylists"]
            uploads_id = related.get("uploads")
            if uploads_id:
                self._channel_playlist_cache[channel_id] = uploads_id
                logger.info(f"Resolved channel {channel_id} → playlist {uploads_id}")
            else:
                logger.warning(f"No uploads playlist for channel {channel_id}")

            return uploads_id

        except HttpError as e:
            logger.error(f"Error resolving channel {channel_id}: {e}")
            return None

    def get_playlist_videos(
        self,
        playlist_id: str,
        max_results: int = 50,
        after_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get videos from a YouTube playlist.

        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum videos to fetch
            after_date: Only include videos published after this date

        Returns:
            List of video metadata dictionaries
        """
        videos: list[dict[str, Any]] = []
        next_page_token = None

        while len(videos) < max_results:
            try:
                request = self.service.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token,
                )
                response = request.execute()

                for item in response.get("items", []):
                    snippet = item["snippet"]
                    content_details = item["contentDetails"]

                    # Parse published date
                    published_str = snippet.get("publishedAt", "")
                    published_date = self._parse_date(published_str)

                    # Filter by date if specified
                    if after_date and published_date < after_date:
                        continue

                    video_data = {
                        "video_id": content_details["videoId"],
                        "title": snippet["title"],
                        "description": snippet.get("description", ""),
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_date": published_date,
                        "thumbnail_url": self._get_best_thumbnail(snippet.get("thumbnails", {})),
                        "playlist_id": playlist_id,
                    }
                    videos.append(video_data)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            except HttpError as e:
                logger.error(f"Error fetching playlist {playlist_id}: {e}")
                raise

        logger.info(f"Found {len(videos)} videos in playlist {playlist_id}")
        return videos[:max_results]

    def get_transcript(
        self,
        video_id: str,
        languages: list[str] | None = None,
    ) -> YouTubeTranscript | None:
        """
        Get transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            languages: Preferred languages (in order)

        Returns:
            YouTubeTranscript object or None if unavailable
        """
        if languages is None:
            languages = DEFAULT_LANGUAGES

        try:
            # Create API instance (v1.2+ API)
            ytt_api = YouTubeTranscriptApi()

            # Try to get transcript in preferred languages
            transcript_list = ytt_api.list(video_id)

            # Try manual transcripts first, then auto-generated
            transcript = None
            is_auto_generated = False

            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except NoTranscriptFound:
                # Fall back to auto-generated
                try:
                    transcript = transcript_list.find_generated_transcript(languages)
                    is_auto_generated = True
                except NoTranscriptFound:
                    # Try any available transcript
                    for t in transcript_list:
                        transcript = t
                        is_auto_generated = t.is_generated
                        break

            if not transcript:
                logger.warning(f"No transcript found for video {video_id}")
                return None

            # Fetch the transcript (returns FetchedTranscript in v1.2+)
            fetched = transcript.fetch()
            language = transcript.language_code

            # Convert to our segment model (v1.2+ returns snippet objects)
            segments = [
                TranscriptSegment(
                    text=snippet.text,
                    start=snippet.start,
                    duration=snippet.duration,
                    is_generated=is_auto_generated,
                )
                for snippet in fetched
            ]

            logger.debug(
                f"Got transcript for {video_id}: {len(segments)} segments, "
                f"language={language}, auto={is_auto_generated}"
            )

            return YouTubeTranscript(
                video_id=video_id,
                title=f"YouTube Video {video_id}",  # Will be updated with actual title
                segments=segments,
                language=language,
                is_auto_generated=is_auto_generated,
            )

        except TranscriptsDisabled:
            logger.warning(f"Transcripts disabled for video {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse ISO 8601 date string."""
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(UTC)

    def _get_best_thumbnail(self, thumbnails: dict[str, Any]) -> str | None:
        """Get highest quality thumbnail URL."""
        for quality in ["maxres", "high", "medium", "default"]:
            if quality in thumbnails:
                url = thumbnails[quality].get("url")
                if isinstance(url, str):
                    return url
        return None


def transcript_to_markdown(transcript: YouTubeTranscript) -> str:
    """Convert a YouTube transcript to markdown with timestamps.

    Creates a markdown document with:
    - Title as H1
    - Video metadata (channel, date, URL)
    - Transcript with timestamp deep-links

    Args:
        transcript: YouTubeTranscript object

    Returns:
        Markdown string
    """
    lines = []

    # Title
    lines.append(f"# {transcript.title}")
    lines.append("")

    # Metadata
    if transcript.channel_title:
        lines.append(f"**Channel:** {transcript.channel_title}")
    if transcript.published_date:
        lines.append(f"**Published:** {transcript.published_date.strftime('%Y-%m-%d')}")
    lines.append(f"**Video:** [{transcript.video_id}]({transcript.video_url})")
    lines.append("")

    # Transcript sections
    lines.append("## Transcript")
    lines.append("")

    # Group segments into paragraphs (by sentence endings or time gaps)
    current_paragraph: list[str] = []
    last_timestamp = 0.0

    for segment in transcript.segments:
        # Start new paragraph if there's a time gap > 5 seconds
        if segment.start - last_timestamp > 5 and current_paragraph:
            timestamp_url = f"{transcript.video_url}&t={int(last_timestamp)}"
            lines.append(f"[{_format_timestamp(last_timestamp)}]({timestamp_url})")
            lines.append(" ".join(current_paragraph))
            lines.append("")
            current_paragraph = []

        current_paragraph.append(segment.text)
        last_timestamp = segment.start

    # Add remaining paragraph
    if current_paragraph:
        timestamp_url = f"{transcript.video_url}&t={int(last_timestamp)}"
        lines.append(f"[{_format_timestamp(last_timestamp)}]({timestamp_url})")
        lines.append(" ".join(current_paragraph))

    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class YouTubeContentIngestionService:
    """Service for ingesting YouTube transcripts into the unified Content model.

    This is the preferred ingestion service for new code. It creates Content
    records with markdown as the primary format, enabling the unified content
    pipeline for summarization and digest creation.
    """

    def __init__(self, use_oauth: bool = True) -> None:
        """Initialize YouTube content ingestion service."""
        self.client = YouTubeClient(use_oauth=use_oauth)

    def ingest_playlist(
        self,
        playlist_id: str,
        max_videos: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
        languages: list[str] | None = None,
    ) -> int:
        """
        Ingest transcripts from a YouTube playlist as Content records.

        Args:
            playlist_id: YouTube playlist ID
            max_videos: Maximum videos to process
            after_date: Only process videos after this date
            force_reprocess: Reprocess existing videos
            languages: Preferred transcript languages

        Returns:
            Number of content items ingested
        """
        logger.info(f"Starting YouTube content ingestion for playlist {playlist_id}...")

        if languages is None:
            languages = DEFAULT_LANGUAGES

        # Get videos from playlist
        videos = self.client.get_playlist_videos(
            playlist_id=playlist_id,
            max_results=max_videos,
            after_date=after_date,
        )

        if not videos:
            logger.info("No videos found in playlist")
            return 0

        # Process each video
        count = 0
        with get_db() as db:
            for video in videos:
                try:
                    # Generate source_id
                    source_id = f"youtube:{video['video_id']}"

                    # Check if already exists in Content table
                    existing = (
                        db.query(Content)
                        .filter(
                            Content.source_type == ContentSource.YOUTUBE,
                            Content.source_id == source_id,
                        )
                        .first()
                    )

                    if existing and not force_reprocess:
                        logger.debug(f"Video already exists: {video['title']}")
                        continue

                    # Get transcript
                    transcript = self.client.get_transcript(video["video_id"], languages)

                    if not transcript:
                        logger.warning(f"No transcript for: {video['title']}")
                        continue

                    # Update transcript with video metadata
                    transcript.title = video["title"]
                    transcript.channel_title = video["channel_title"]
                    transcript.published_date = video["published_date"]
                    transcript.thumbnail_url = video.get("thumbnail_url")
                    transcript.playlist_id = video.get("playlist_id")

                    # Convert to markdown
                    markdown_content = transcript_to_markdown(transcript)

                    # Store raw transcript as JSON for re-parsing
                    raw_content = json.dumps(transcript.to_storage_dict())

                    # Generate content hash from markdown
                    content_hash = generate_markdown_hash(markdown_content)

                    # Check for content duplicate
                    content_duplicate = None
                    if not existing and content_hash:
                        content_duplicate = (
                            db.query(Content).filter(Content.content_hash == content_hash).first()
                        )

                    video_url = transcript.video_url

                    # Build metadata
                    metadata_json = {
                        "video_id": video["video_id"],
                        "playlist_id": playlist_id,
                        "language": transcript.language,
                        "is_auto_generated": transcript.is_auto_generated,
                        "segment_count": len(transcript.segments),
                        "duration_seconds": sum(s.duration for s in transcript.segments),
                        "thumbnail_url": video.get("thumbnail_url"),
                    }

                    # Optional: Extract keyframes
                    if settings.youtube_keyframe_extraction:
                        metadata_json = self._extract_keyframes(
                            video_id=video["video_id"],
                            transcript=transcript,
                            metadata_json=metadata_json,
                        )

                    if existing and force_reprocess:
                        # Update existing
                        existing.title = video["title"]
                        existing.author = video["channel_title"]
                        existing.publication = video["channel_title"]
                        existing.published_date = video["published_date"]
                        existing.source_url = video_url
                        existing.markdown_content = markdown_content
                        existing.raw_content = raw_content
                        existing.raw_format = "transcript_json"
                        existing.metadata_json = metadata_json
                        existing.content_hash = content_hash
                        existing.parser_used = "youtube_transcript_api"
                        existing.status = ContentStatus.PARSED
                        existing.error_message = None
                        count += 1
                        logger.info(f"Updated for reprocessing: {video['title']}")

                    elif content_duplicate:
                        # Link to canonical
                        content = Content(
                            source_type=ContentSource.YOUTUBE,
                            source_id=source_id,
                            source_url=video_url,
                            title=video["title"],
                            author=video["channel_title"],
                            publication=video["channel_title"],
                            published_date=video["published_date"],
                            markdown_content=markdown_content,
                            raw_content=raw_content,
                            raw_format="transcript_json",
                            metadata_json=metadata_json,
                            parser_used="youtube_transcript_api",
                            content_hash=content_hash,
                            canonical_id=content_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Linked duplicate: {video['title']}")

                    else:
                        # Create new
                        content = Content(
                            source_type=ContentSource.YOUTUBE,
                            source_id=source_id,
                            source_url=video_url,
                            title=video["title"],
                            author=video["channel_title"],
                            publication=video["channel_title"],
                            published_date=video["published_date"],
                            markdown_content=markdown_content,
                            raw_content=raw_content,
                            raw_format="transcript_json",
                            metadata_json=metadata_json,
                            parser_used="youtube_transcript_api",
                            content_hash=content_hash,
                            status=ContentStatus.PARSED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Ingested: {video['title']}")

                except Exception as e:
                    logger.error(f"Error processing video {video.get('title', 'unknown')}: {e}")
                    db.rollback()
                    continue

        logger.info(f"Successfully ingested {count} content items")
        return count

    def ingest_all_playlists(
        self,
        sources: list[YouTubePlaylistSource] | None = None,
        playlist_ids: list[str] | None = None,
        max_videos_per_playlist: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """Ingest transcripts from multiple playlists as Content records.

        Source resolution (in priority order):
        1. sources parameter (YouTubePlaylistSource objects)
        2. playlist_ids parameter (backward compatible)
        3. SourcesConfig (YAML files)
        4. Legacy settings (youtube_playlists.txt)

        Sources with visibility='private' are skipped when OAuth is unavailable.
        """
        # --- Source resolution ---
        resolved_sources: list[YouTubePlaylistSource] = []

        if sources is not None:
            resolved_sources = [s for s in sources if s.enabled]
        elif playlist_ids is not None:
            # Backward compatibility: wrap raw IDs as source objects
            from src.config.sources import YouTubePlaylistSource as YTSource

            resolved_sources = [YTSource(id=pid) for pid in playlist_ids if pid]
        else:
            # Try SourcesConfig first
            config = settings.get_sources_config()
            resolved_sources = config.get_youtube_playlist_sources()

            if not resolved_sources:
                # Fall back to legacy settings
                legacy = settings.get_youtube_playlists()
                if legacy:
                    from src.config.sources import YouTubePlaylistSource as YTSource

                    resolved_sources = [
                        YTSource(id=p["id"], name=p.get("description")) for p in legacy if p["id"]
                    ]

        if not resolved_sources:
            logger.warning("No YouTube playlists configured")
            return 0

        # --- Visibility filtering ---
        skipped_private = 0
        total = 0
        for source in resolved_sources:
            if source.visibility == "private" and not self.client.oauth_available:
                skipped_private += 1
                logger.warning(
                    f"Skipping private playlist '{source.name or source.id}' (OAuth not available)"
                )
                continue

            try:
                max_videos = source.max_entries or max_videos_per_playlist
                count = self.ingest_playlist(
                    playlist_id=source.id,
                    max_videos=max_videos,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                )
                total += count
            except Exception as e:
                logger.error(f"Error ingesting playlist {source.name or source.id}: {e}")
                continue

        if skipped_private:
            logger.info(f"Skipped {skipped_private} private playlist(s) due to missing OAuth")

        return total

    def ingest_channels(
        self,
        sources: list[YouTubeChannelSource] | None = None,
        max_videos_per_channel: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """Ingest transcripts from YouTube channels by resolving to uploads playlists.

        Each channel is resolved to its uploads playlist via the YouTube Data API,
        then ingested using the same playlist ingestion logic.

        Source resolution:
        1. sources parameter (YouTubeChannelSource objects)
        2. SourcesConfig (YAML files)

        Sources with visibility='private' are skipped when OAuth is unavailable.
        """
        # --- Source resolution ---
        resolved_sources: list[YouTubeChannelSource] = []

        if sources is not None:
            resolved_sources = [s for s in sources if s.enabled]
        else:
            config = settings.get_sources_config()
            resolved_sources = config.get_youtube_channel_sources()

        if not resolved_sources:
            logger.info("No YouTube channels configured")
            return 0

        # --- Resolve and ingest ---
        skipped_private = 0
        total = 0
        for source in resolved_sources:
            if source.visibility == "private" and not self.client.oauth_available:
                skipped_private += 1
                logger.warning(
                    f"Skipping private channel '{source.name or source.channel_id}' "
                    "(OAuth not available)"
                )
                continue

            # Resolve channel to uploads playlist
            playlist_id = self.client.resolve_channel_to_playlist(source.channel_id)
            if not playlist_id:
                logger.warning(
                    f"Could not resolve channel '{source.name or source.channel_id}' "
                    "to uploads playlist, skipping"
                )
                continue

            try:
                max_videos = source.max_entries or max_videos_per_channel
                count = self.ingest_playlist(
                    playlist_id=playlist_id,
                    max_videos=max_videos,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                    languages=source.languages,
                )
                total += count
            except Exception as e:
                logger.error(f"Error ingesting channel {source.name or source.channel_id}: {e}")
                continue

        if skipped_private:
            logger.info(f"Skipped {skipped_private} private channel(s) due to missing OAuth")

        return total

    def _extract_keyframes(
        self,
        video_id: str,
        transcript: YouTubeTranscript,
        metadata_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract keyframes from a video and add to metadata."""
        try:
            from src.ingestion.youtube_keyframes import KeyframeExtractor

            extractor = KeyframeExtractor()

            if not extractor.is_available():
                logger.warning("Keyframe extraction skipped: ffmpeg not available")
                return metadata_json

            segments = [
                {"text": seg.text, "start": seg.start, "duration": seg.duration}
                for seg in transcript.segments
            ]

            result = extractor.extract_keyframes_for_video(
                video_id=video_id,
                transcript_segments=segments,
            )

            if result.error:
                logger.warning(f"Keyframe extraction failed: {result.error}")
                return metadata_json

            if result.slides:
                slide_data = []
                for slide in result.slides:
                    closest_segment = min(
                        segments,
                        key=lambda s: abs(s["start"] - slide.timestamp),
                    )

                    slide_data.append(
                        {
                            "frame_path": slide.path,
                            "timestamp": slide.timestamp,
                            "timestamp_url": f"https://youtube.com/watch?v={video_id}&t={int(slide.timestamp)}",
                            "transcript_text": closest_segment["text"],
                            "hash": slide.hash_value,
                        }
                    )

                metadata_json["slides"] = slide_data
                metadata_json["slide_count"] = result.slide_count
                metadata_json["extraction_method"] = result.extraction_method

                logger.info(f"Added {result.slide_count} keyframes to metadata")

        except ImportError:
            logger.warning("Keyframe extraction skipped: dependencies not installed")
        except Exception as e:
            logger.error(f"Keyframe extraction error: {e}")

        return metadata_json


class YouTubeRSSIngestionService:
    """Service for ingesting YouTube videos discovered via RSS/Atom feeds.

    YouTube channels provide Atom feeds at:
    https://www.youtube.com/feeds/videos.xml?channel_id=UC...

    This service parses these feeds to discover new videos, then fetches
    transcripts using the YouTube Transcript API (no YouTube Data API quota used
    for discovery).
    """

    def __init__(self) -> None:
        """Initialize YouTube RSS ingestion service."""
        self.client = YouTubeClient(use_oauth=False)

    def _parse_feed(self, feed_url: str, max_entries: int = 10) -> list[dict[str, Any]]:
        """Parse a YouTube RSS/Atom feed and extract video metadata.

        Args:
            feed_url: URL of the YouTube RSS feed
            max_entries: Maximum entries to process

        Returns:
            List of dicts with video_id, title, published_date, channel_title, link
        """
        import feedparser

        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse YouTube RSS feed: {feed_url}")
            return []

        videos = []
        for entry in feed.entries[:max_entries]:
            # YouTube Atom feeds include video ID in yt:videoId tag
            video_id = entry.get("yt_videoid")
            if not video_id:
                # Fallback: extract from link
                link = entry.get("link", "")
                if "watch?v=" in link:
                    video_id = link.split("watch?v=")[1].split("&")[0]

            if not video_id:
                continue

            # Parse published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                except (TypeError, ValueError):
                    pass

            videos.append(
                {
                    "video_id": video_id,
                    "title": entry.get("title", ""),
                    "channel_title": entry.get("author", feed.feed.get("title", "")),
                    "published_date": published,
                    "link": entry.get("link", ""),
                }
            )

        return videos

    def ingest_feed(
        self,
        feed_url: str,
        max_entries: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
        source_name: str | None = None,
        source_tags: list[str] | None = None,
    ) -> int:
        """Ingest videos from a single YouTube RSS feed.

        Args:
            feed_url: YouTube RSS feed URL
            max_entries: Maximum videos to process
            after_date: Only include videos published after this date
            force_reprocess: Re-fetch already existing videos
            source_name: Optional name for metadata
            source_tags: Optional tags for metadata

        Returns:
            Number of content items ingested
        """
        videos = self._parse_feed(feed_url, max_entries=max_entries)

        if not videos:
            logger.info(f"No videos found in RSS feed: {feed_url}")
            return 0

        count = 0
        with get_db() as db:
            for video in videos:
                video_id = video["video_id"]
                source_id = f"youtube:{video_id}"

                # Date filter
                if (
                    after_date
                    and video.get("published_date")
                    and video["published_date"] < after_date
                ):
                    continue

                # Dedup check
                if not force_reprocess:
                    existing = db.query(Content).filter(Content.source_id == source_id).first()
                    if existing:
                        logger.debug(f"Skipping existing video: {video_id}")
                        continue

                # Fetch transcript
                transcript = self.client.get_transcript(video_id)
                if not transcript:
                    logger.info(f"No transcript available for {video_id}: {video['title']}")
                    continue

                # Enrich transcript with feed metadata
                if not transcript.title and video.get("title"):
                    transcript.title = video["title"]
                if not transcript.channel_title and video.get("channel_title"):
                    transcript.channel_title = video["channel_title"]
                if not transcript.published_date and video.get("published_date"):
                    transcript.published_date = video["published_date"]

                # Convert to markdown
                markdown_content = transcript_to_markdown(transcript)
                content_hash = generate_markdown_hash(markdown_content)

                # Build metadata
                metadata: dict[str, Any] = {
                    "video_id": video_id,
                    "language": transcript.language,
                    "is_auto_generated": transcript.is_auto_generated,
                    "segment_count": len(transcript.segments),
                    "duration_seconds": transcript.duration_seconds,
                    "thumbnail_url": transcript.thumbnail_url,
                    "feed_url": feed_url,
                    "discovery_method": "rss",
                }
                if source_name:
                    metadata["source_name"] = source_name
                if source_tags:
                    metadata["source_tags"] = source_tags

                try:
                    content = Content(
                        source_type=ContentSource.YOUTUBE,
                        source_id=source_id,
                        title=transcript.title or video.get("title", f"Video {video_id}"),
                        source_url=f"https://www.youtube.com/watch?v={video_id}",
                        raw_content=json.dumps(transcript.to_storage_dict()),
                        raw_format="transcript_json",
                        markdown_content=markdown_content,
                        content_hash=content_hash,
                        parser_used="youtube_transcript_api",
                        status=ContentStatus.PARSED,
                        published_date=video.get("published_date"),
                        metadata_json=metadata,
                    )
                    db.add(content)
                    db.commit()
                    count += 1
                    logger.info(f"Ingested YouTube RSS video: {video['title']}")
                except Exception as e:
                    logger.error(f"Error creating content for video {video_id}: {e}")
                    db.rollback()
                    continue

        return count

    def ingest_all_feeds(
        self,
        sources: list[YouTubeRSSSource] | None = None,
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """Ingest videos from multiple YouTube RSS feeds.

        Source resolution:
        1. sources parameter (YouTubeRSSSource objects)
        2. SourcesConfig (YAML files)
        """
        resolved_sources: list[YouTubeRSSSource] = []

        if sources is not None:
            resolved_sources = [s for s in sources if s.enabled]
        else:
            config = settings.get_sources_config()
            resolved_sources = config.get_youtube_rss_sources()

        if not resolved_sources:
            logger.info("No YouTube RSS feeds configured")
            return 0

        logger.info(f"Processing {len(resolved_sources)} YouTube RSS feed(s)")

        total = 0
        for i, source in enumerate(resolved_sources, 1):
            feed_label = source.name or source.url
            logger.debug(f"[{i}/{len(resolved_sources)}] Fetching RSS feed: {feed_label}")
            try:
                max_entries = source.max_entries or max_entries_per_feed
                count = self.ingest_feed(
                    feed_url=source.url,
                    max_entries=max_entries,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                    source_name=source.name,
                    source_tags=source.tags if source.tags else None,
                )
                total += count
            except Exception as e:
                logger.error(f"Error ingesting YouTube RSS feed {feed_label}: {e}")
                continue

        logger.info(
            f"YouTube RSS feed ingestion complete: {total} item(s) from {len(resolved_sources)} feed(s)"
        )
        return total


def main() -> None:
    """CLI entry point for YouTube ingestion (deprecated).

    Uses the unified Content model for all ingestion by default.

    .. deprecated::
        Use ``aca ingest youtube`` instead of ``python -m src.ingestion.youtube``.
    """
    import warnings

    warnings.warn(
        "Running 'python -m src.ingestion.youtube' is deprecated. "
        "Use 'aca ingest youtube' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    parser = argparse.ArgumentParser(description="Ingest YouTube transcripts")
    parser.add_argument(
        "--playlist-id",
        type=str,
        help="YouTube playlist ID (uses config if not specified)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=10,
        help="Maximum videos to process per playlist",
    )
    parser.add_argument(
        "--after-date",
        type=str,
        help="Only process videos after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocess existing videos",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Use API key instead of OAuth (public playlists only)",
    )

    args = parser.parse_args()

    # Parse date if provided
    after_date = None
    if args.after_date:
        after_date = datetime.strptime(args.after_date, "%Y-%m-%d").replace(tzinfo=UTC)

    # Create service (uses unified Content model)
    service = YouTubeContentIngestionService(use_oauth=not args.public_only)

    # Ingest
    if args.playlist_id:
        count = service.ingest_playlist(
            playlist_id=args.playlist_id,
            max_videos=args.max_videos,
            after_date=after_date,
            force_reprocess=args.force,
        )
    else:
        count = service.ingest_all_playlists(
            max_videos_per_playlist=args.max_videos,
            after_date=after_date,
            force_reprocess=args.force,
        )

    print(f"Ingested {count} content items")


if __name__ == "__main__":
    main()
