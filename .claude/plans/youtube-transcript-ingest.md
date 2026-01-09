# YouTube Transcript Ingestion - Implementation Plan

## Overview

Add the ability to ingest transcripts from YouTube playlists (both private and public) as a new content source for the newsletter aggregator. This follows the existing ingestion patterns used by Gmail and RSS modules.

## Goals

1. **Primary**: Ingest transcripts from YouTube videos in specified playlists
2. **Primary**: Support both public playlists (API key) and private playlists (OAuth)
3. **Primary**: Preserve timestamps for deep-linking to specific video sections
4. **Bonus**: Extract key frames that correspond to slides for visual context

## Timestamp Deep-Linking Requirements

YouTube supports deep-linking to specific timestamps using the `?t=` parameter:
- `https://www.youtube.com/watch?v=VIDEO_ID&t=125` (125 seconds)
- `https://youtu.be/VIDEO_ID?t=125` (short format)

The system should:
1. Store transcript segments with their start/end timestamps
2. Enable summaries to reference specific quotes with timestamps
3. Generate deep-link URLs for embedding or direct navigation
4. Support future embedded player with timestamp-based playback

## Architecture

### Component Overview

```
src/
  ingestion/
    youtube.py              # NEW: YouTube client and ingestion service
  models/
    newsletter.py           # UPDATE: Add YOUTUBE source type
    youtube.py              # NEW: YouTube-specific models for timestamps
  utils/
    youtube_links.py        # NEW: Timestamp URL generation utilities
  config/
    settings.py             # UPDATE: Add YouTube configuration
```

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Transcript API** | `youtube-transcript-api` | No API quota cost, no auth needed, simple to use |
| **Playlist Access** | `google-api-python-client` | Official Google library, handles OAuth, same as Gmail |
| **Keyframe Extraction** | `katna` + `yt-dlp` | Best Python libraries for this purpose |
| **Storage Model** | Extend `Newsletter` model | Consistent with existing pipeline, minimal changes |
| **Auth Pattern** | Reuse Gmail OAuth pattern | Unified credential management |

---

## Implementation Steps

### Phase 1: Core Infrastructure

#### Step 1.1: Add YouTube Source Type

**File**: `src/models/newsletter.py`

```python
class NewsletterSource(str, Enum):
    GMAIL = "gmail"
    RSS = "rss"
    SUBSTACK_RSS = "substack_rss"
    YOUTUBE = "youtube"  # NEW
    OTHER = "other"
```

#### Step 1.2: Add Configuration Settings

**File**: `src/config/settings.py`

Add new settings:
```python
# YouTube configuration
youtube_credentials_file: str = "youtube_credentials.json"
youtube_token_file: str = "youtube_token.json"
youtube_playlists: list[str] = []  # Playlist IDs to monitor
youtube_api_key: str | None = None  # For public playlists only
youtube_keyframe_extraction: bool = False  # Enable/disable keyframe extraction
youtube_temp_dir: str = "/tmp/youtube_downloads"  # Temp storage for video downloads
youtube_slide_similarity_threshold: float = 0.85  # 0-1, higher = stricter dedup
```

**Environment variables** (`.env`):
```bash
YOUTUBE_API_KEY=AIza...           # Optional: for public playlists only
YOUTUBE_PLAYLISTS=PLxxx,PLyyy     # Comma-separated playlist IDs
YOUTUBE_KEYFRAME_EXTRACTION=false # Enable keyframe extraction
YOUTUBE_SLIDE_SIMILARITY_THRESHOLD=0.85  # Slide dedup threshold (0-1)
```

#### Step 1.3: Install Dependencies

**File**: `pyproject.toml` or `requirements.txt`

```
youtube-transcript-api>=0.6.0
google-api-python-client>=2.100.0  # Already present for Gmail
google-auth-oauthlib>=1.0.0        # Already present for Gmail
yt-dlp>=2024.1.0                   # For video downloads (keyframes)
katna>=0.10.0                      # For keyframe extraction
```

#### Step 1.4: Create YouTube-Specific Models

**File**: `src/models/youtube.py`

```python
"""YouTube-specific data models for timestamped transcripts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field


class TranscriptSegment(BaseModel):
    """A single segment of a YouTube transcript with timestamp."""

    text: str
    start: float  # Start time in seconds
    duration: float  # Duration in seconds
    is_generated: bool = False  # True if auto-generated captions

    @computed_field
    @property
    def end(self) -> float:
        """End time in seconds."""
        return self.start + self.duration

    @computed_field
    @property
    def start_formatted(self) -> str:
        """Human-readable start time (HH:MM:SS or MM:SS)."""
        return format_timestamp(self.start)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "text": self.text,
            "start": self.start,
            "duration": self.duration,
            "end": self.end,
            "is_generated": self.is_generated,
        }


class YouTubeTranscript(BaseModel):
    """Full transcript with metadata and timestamped segments."""

    video_id: str
    title: str
    channel_title: str
    published_date: datetime
    duration_seconds: float | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str = "en"
    is_auto_generated: bool = False
    thumbnail_url: str | None = None
    playlist_id: str | None = None

    @computed_field
    @property
    def full_text(self) -> str:
        """Concatenated transcript text."""
        return " ".join(seg.text for seg in self.segments)

    @computed_field
    @property
    def video_url(self) -> str:
        """Standard YouTube video URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def get_url_at_timestamp(self, seconds: float) -> str:
        """Get video URL that starts at specific timestamp."""
        return f"{self.video_url}&t={int(seconds)}"

    def get_segment_at_time(self, seconds: float) -> TranscriptSegment | None:
        """Find the transcript segment at a given timestamp."""
        for seg in self.segments:
            if seg.start <= seconds < seg.end:
                return seg
        return None

    def get_segments_in_range(
        self, start: float, end: float
    ) -> list[TranscriptSegment]:
        """Get all segments within a time range."""
        return [
            seg for seg in self.segments
            if seg.start >= start and seg.start < end
        ]

    def search_text(self, query: str) -> list[tuple[TranscriptSegment, str]]:
        """
        Search transcript for text matches.

        Returns list of (segment, url_with_timestamp) tuples.
        """
        query_lower = query.lower()
        results = []
        for seg in self.segments:
            if query_lower in seg.text.lower():
                url = self.get_url_at_timestamp(seg.start)
                results.append((seg, url))
        return results

    def to_storage_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "type": "youtube_transcript",
            "video_id": self.video_id,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "is_auto_generated": self.is_auto_generated,
            "thumbnail_url": self.thumbnail_url,
            "playlist_id": self.playlist_id,
            "segments": [seg.to_dict() for seg in self.segments],
            "segment_count": len(self.segments),
        }


class TimestampedQuote(BaseModel):
    """A quote from a video with timestamp for linking."""

    text: str
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float | None = None
    context: str | None = None  # Surrounding text for context

    @computed_field
    @property
    def timestamp_url(self) -> str:
        """URL that links directly to this quote in the video."""
        return f"https://www.youtube.com/watch?v={self.video_id}&t={int(self.start_seconds)}"

    @computed_field
    @property
    def embed_url(self) -> str:
        """Embed URL for iframe with start time."""
        return f"https://www.youtube.com/embed/{self.video_id}?start={int(self.start_seconds)}"

    @computed_field
    @property
    def timestamp_display(self) -> str:
        """Human-readable timestamp."""
        return format_timestamp(self.start_seconds)

    def to_markdown_link(self) -> str:
        """Format as markdown link with timestamp."""
        return f"[{self.timestamp_display}]({self.timestamp_url})"


def format_timestamp(seconds: float) -> str:
    """
    Format seconds as human-readable timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string (HH:MM:SS or MM:SS)
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_timestamp(timestamp: str) -> float:
    """
    Parse human-readable timestamp to seconds.

    Args:
        timestamp: String like "1:23:45" or "5:30"

    Returns:
        Time in seconds
    """
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    else:
        return float(parts[0])
```

#### Step 1.5: Create YouTube URL Utilities

**File**: `src/utils/youtube_links.py`

```python
"""Utilities for YouTube URL generation and parsing."""

import re
from typing import NamedTuple


class VideoReference(NamedTuple):
    """Parsed YouTube video reference."""

    video_id: str
    timestamp: float | None


def extract_video_id(url: str) -> str | None:
    """
    Extract video ID from various YouTube URL formats.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_timestamp(url: str) -> float | None:
    """
    Extract timestamp from YouTube URL.

    Supports:
    - ?t=125 (seconds)
    - ?t=2m5s (2 minutes 5 seconds)
    - &t=125
    """
    # Try seconds format
    match = re.search(r'[?&]t=(\d+)', url)
    if match:
        return float(match.group(1))

    # Try HhMmSs format
    match = re.search(r'[?&]t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', url)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        if hours or minutes or seconds:
            return float(hours * 3600 + minutes * 60 + seconds)

    return None


def parse_youtube_url(url: str) -> VideoReference | None:
    """
    Parse a YouTube URL into video ID and optional timestamp.

    Args:
        url: YouTube URL

    Returns:
        VideoReference with video_id and optional timestamp
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    timestamp = extract_timestamp(url)
    return VideoReference(video_id=video_id, timestamp=timestamp)


def build_video_url(
    video_id: str,
    timestamp: float | None = None,
    short: bool = False,
) -> str:
    """
    Build a YouTube video URL.

    Args:
        video_id: YouTube video ID
        timestamp: Optional start time in seconds
        short: Use youtu.be short format

    Returns:
        YouTube URL
    """
    if short:
        base = f"https://youtu.be/{video_id}"
        if timestamp:
            return f"{base}?t={int(timestamp)}"
        return base
    else:
        base = f"https://www.youtube.com/watch?v={video_id}"
        if timestamp:
            return f"{base}&t={int(timestamp)}"
        return base


def build_embed_url(
    video_id: str,
    start: float | None = None,
    end: float | None = None,
    autoplay: bool = False,
) -> str:
    """
    Build a YouTube embed URL for iframe.

    Args:
        video_id: YouTube video ID
        start: Optional start time in seconds
        end: Optional end time in seconds
        autoplay: Auto-start video

    Returns:
        Embed URL for iframe src
    """
    params = []
    if start:
        params.append(f"start={int(start)}")
    if end:
        params.append(f"end={int(end)}")
    if autoplay:
        params.append("autoplay=1")

    base = f"https://www.youtube.com/embed/{video_id}"
    if params:
        return f"{base}?{'&'.join(params)}"
    return base


def build_embed_html(
    video_id: str,
    start: float | None = None,
    end: float | None = None,
    width: int = 560,
    height: int = 315,
    title: str = "YouTube video player",
) -> str:
    """
    Build complete HTML for embedded YouTube player.

    Args:
        video_id: YouTube video ID
        start: Optional start time
        end: Optional end time
        width: Player width
        height: Player height
        title: Iframe title for accessibility

    Returns:
        HTML string for embedding
    """
    embed_url = build_embed_url(video_id, start, end)

    return f'''<iframe
    width="{width}"
    height="{height}"
    src="{embed_url}"
    title="{title}"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen
></iframe>'''


def format_quote_with_link(
    quote: str,
    video_id: str,
    timestamp: float,
    video_title: str | None = None,
) -> str:
    """
    Format a quote with a timestamp link for use in digests.

    Args:
        quote: The quoted text
        video_id: YouTube video ID
        timestamp: Time of quote in seconds
        video_title: Optional video title

    Returns:
        Markdown-formatted quote with link
    """
    from src.models.youtube import format_timestamp

    url = build_video_url(video_id, timestamp)
    time_str = format_timestamp(timestamp)

    if video_title:
        return f'> "{quote}"\n> — [{video_title} @ {time_str}]({url})'
    else:
        return f'> "{quote}"\n> — [@ {time_str}]({url})'
```

---

### Phase 2: YouTube Client Implementation

#### Step 2.1: Create YouTube Client

**File**: `src/ingestion/youtube.py`

```python
"""YouTube transcript ingestion."""

import os
from datetime import datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from src.config import settings
from src.models.newsletter import Newsletter, NewsletterData, NewsletterSource, ProcessingStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_content_hash
from src.utils.logging import get_logger

logger = get_logger(__name__)

# YouTube API scopes (for private playlists)
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


class YouTubeClient:
    """YouTube API client for fetching playlist videos and transcripts."""

    def __init__(self, use_oauth: bool = True) -> None:
        """
        Initialize YouTube client.

        Args:
            use_oauth: If True, use OAuth for private playlist access.
                       If False, use API key for public playlists only.
        """
        self.service = None
        self.use_oauth = use_oauth
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with YouTube API."""
        if self.use_oauth:
            self._authenticate_oauth()
        else:
            self._authenticate_api_key()

    def _authenticate_oauth(self) -> None:
        """Authenticate using OAuth2 (for private playlists)."""
        creds = None

        # Load existing credentials
        if os.path.exists(settings.youtube_token_file):
            creds = Credentials.from_authorized_user_file(
                settings.youtube_token_file, SCOPES
            )

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

        self.service = build("youtube", "v3", credentials=creds)
        logger.info("YouTube API client initialized (OAuth)")

    def _authenticate_api_key(self) -> None:
        """Authenticate using API key (for public playlists only)."""
        if not settings.youtube_api_key:
            raise ValueError("YOUTUBE_API_KEY required for public playlist access")

        self.service = build(
            "youtube", "v3",
            developerKey=settings.youtube_api_key
        )
        logger.info("YouTube API client initialized (API key)")

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
        videos = []
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
        languages: list[str] = ["en"],
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """
        Get transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            languages: Preferred languages (in order)

        Returns:
            Tuple of (full_text, transcript_segments) or None if unavailable
        """
        try:
            # Try to get transcript in preferred languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try manual transcripts first, then auto-generated
            transcript = None
            try:
                transcript = transcript_list.find_transcript(languages)
            except NoTranscriptFound:
                # Fall back to auto-generated
                try:
                    transcript = transcript_list.find_generated_transcript(languages)
                except NoTranscriptFound:
                    # Try any available transcript
                    for t in transcript_list:
                        transcript = t
                        break

            if not transcript:
                logger.warning(f"No transcript found for video {video_id}")
                return None

            # Fetch the transcript
            segments = transcript.fetch()

            # Combine into full text
            full_text = " ".join(segment["text"] for segment in segments)

            logger.debug(f"Got transcript for {video_id}: {len(segments)} segments, {len(full_text)} chars")
            return full_text, segments

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
            return datetime.utcnow()

    def _get_best_thumbnail(self, thumbnails: dict) -> str | None:
        """Get highest quality thumbnail URL."""
        for quality in ["maxres", "high", "medium", "default"]:
            if quality in thumbnails:
                return thumbnails[quality].get("url")
        return None
```

#### Step 2.2: Create YouTube Ingestion Service

**File**: `src/ingestion/youtube.py` (continued)

```python
class YouTubeIngestionService:
    """Service for ingesting YouTube transcripts."""

    def __init__(self, use_oauth: bool = True) -> None:
        """Initialize YouTube ingestion service."""
        self.client = YouTubeClient(use_oauth=use_oauth)

    def ingest_playlist(
        self,
        playlist_id: str,
        max_videos: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
        languages: list[str] = ["en"],
    ) -> int:
        """
        Ingest transcripts from a YouTube playlist.

        Args:
            playlist_id: YouTube playlist ID
            max_videos: Maximum videos to process
            after_date: Only process videos after this date
            force_reprocess: Reprocess existing videos
            languages: Preferred transcript languages

        Returns:
            Number of transcripts ingested
        """
        logger.info(f"Starting YouTube ingestion for playlist {playlist_id}...")

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

                    # Check if already exists
                    existing = (
                        db.query(Newsletter)
                        .filter(Newsletter.source_id == source_id)
                        .first()
                    )

                    if existing and not force_reprocess:
                        logger.debug(f"Video already exists: {video['title']}")
                        continue

                    # Get transcript
                    transcript_result = self.client.get_transcript(
                        video["video_id"], languages
                    )

                    if not transcript_result:
                        logger.warning(f"No transcript for: {video['title']}")
                        continue

                    full_text, segments = transcript_result

                    # Generate content hash
                    content_hash = generate_content_hash(full_text)

                    # Check for content duplicate
                    content_duplicate = None
                    if not existing and content_hash:
                        content_duplicate = (
                            db.query(Newsletter)
                            .filter(Newsletter.content_hash == content_hash)
                            .first()
                        )

                    # Build metadata
                    video_url = f"https://www.youtube.com/watch?v={video['video_id']}"

                    # Store transcript segments as JSON in extracted_links
                    # (repurposing this field for transcript metadata)
                    transcript_metadata = {
                        "type": "youtube_transcript",
                        "segments": segments[:100],  # Store first 100 segments
                        "total_segments": len(segments),
                        "thumbnail_url": video.get("thumbnail_url"),
                        "playlist_id": video.get("playlist_id"),
                    }

                    if existing and force_reprocess:
                        # Update existing
                        existing.title = video["title"]
                        existing.sender = video["channel_title"]
                        existing.publication = video["channel_title"]
                        existing.published_date = video["published_date"]
                        existing.url = video_url
                        existing.raw_html = None
                        existing.raw_text = full_text
                        existing.extracted_links = transcript_metadata
                        existing.content_hash = content_hash
                        existing.status = ProcessingStatus.PENDING
                        existing.error_message = None
                        count += 1
                        logger.info(f"Updated for reprocessing: {video['title']}")

                    elif content_duplicate:
                        # Link to canonical
                        newsletter = Newsletter(
                            source=NewsletterSource.YOUTUBE,
                            source_id=source_id,
                            title=video["title"],
                            sender=video["channel_title"],
                            publication=video["channel_title"],
                            published_date=video["published_date"],
                            url=video_url,
                            raw_html=None,
                            raw_text=full_text,
                            extracted_links=transcript_metadata,
                            content_hash=content_hash,
                            canonical_newsletter_id=content_duplicate.id,
                            status=ProcessingStatus.COMPLETED,
                        )
                        db.add(newsletter)
                        count += 1
                        logger.info(f"Linked duplicate: {video['title']}")

                    else:
                        # Create new
                        newsletter = Newsletter(
                            source=NewsletterSource.YOUTUBE,
                            source_id=source_id,
                            title=video["title"],
                            sender=video["channel_title"],
                            publication=video["channel_title"],
                            published_date=video["published_date"],
                            url=video_url,
                            raw_html=None,
                            raw_text=full_text,
                            extracted_links=transcript_metadata,
                            content_hash=content_hash,
                            status=ProcessingStatus.PENDING,
                        )
                        db.add(newsletter)
                        count += 1
                        logger.info(f"Ingested: {video['title']}")

                except Exception as e:
                    logger.error(f"Error processing video {video.get('title', 'unknown')}: {e}")
                    db.rollback()
                    continue

        logger.info(f"Successfully ingested {count} transcripts")
        return count

    def ingest_all_playlists(
        self,
        playlist_ids: list[str] | None = None,
        max_videos_per_playlist: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """
        Ingest transcripts from multiple playlists.

        Args:
            playlist_ids: List of playlist IDs (uses config if None)
            max_videos_per_playlist: Max videos per playlist
            after_date: Only process videos after this date
            force_reprocess: Reprocess existing videos

        Returns:
            Total number of transcripts ingested
        """
        if playlist_ids is None:
            playlist_ids = settings.youtube_playlists

        if not playlist_ids:
            logger.warning("No YouTube playlists configured")
            return 0

        total = 0
        for playlist_id in playlist_ids:
            try:
                count = self.ingest_playlist(
                    playlist_id=playlist_id,
                    max_videos=max_videos_per_playlist,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                )
                total += count
            except Exception as e:
                logger.error(f"Error ingesting playlist {playlist_id}: {e}")
                continue

        return total
```

---

### Phase 3: CLI Interface

#### Step 3.1: Create CLI Entry Point

**File**: `src/ingestion/youtube.py` (add at end)

```python
def main() -> None:
    """CLI entry point for YouTube ingestion."""
    import argparse

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
        after_date = datetime.strptime(args.after_date, "%Y-%m-%d")

    # Create service
    service = YouTubeIngestionService(use_oauth=not args.public_only)

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

    print(f"Ingested {count} transcripts")


if __name__ == "__main__":
    main()
```

**Usage**:
```bash
# Ingest from configured playlists
python -m src.ingestion.youtube

# Ingest specific playlist
python -m src.ingestion.youtube --playlist-id PLxxxxxxx --max-videos 20

# Force reprocess
python -m src.ingestion.youtube --playlist-id PLxxxxxxx --force

# Public playlists only (no OAuth)
python -m src.ingestion.youtube --playlist-id PLxxxxxxx --public-only
```

---

### Phase 4: Keyframe Extraction (Bonus Feature)

#### Step 4.1: Keyframe Extractor Module

**File**: `src/ingestion/youtube_keyframes.py`

```python
"""YouTube keyframe extraction for slide detection with deduplication."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import NamedTuple

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default similarity threshold (0-1, higher = more similar required to consider duplicate)
DEFAULT_SIMILARITY_THRESHOLD = 0.85


class SlideFrame(NamedTuple):
    """A unique slide frame with metadata."""

    path: str
    timestamp: float
    hash_value: str
    is_representative: bool = True  # True if this is the representative frame for a slide


class KeyframeExtractor:
    """Extract keyframes from YouTube videos for slide detection."""

    def __init__(self, output_dir: str | None = None) -> None:
        """
        Initialize keyframe extractor.

        Args:
            output_dir: Directory to store extracted keyframes
        """
        self.output_dir = output_dir or settings.youtube_temp_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def download_video(self, video_id: str) -> str | None:
        """
        Download a YouTube video for processing.

        Args:
            video_id: YouTube video ID

        Returns:
            Path to downloaded video or None if failed
        """
        try:
            import yt_dlp

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            output_path = os.path.join(self.output_dir, f"{video_id}.mp4")

            ydl_opts = {
                "format": "worst[ext=mp4]",  # Use lowest quality to save bandwidth
                "outtmpl": output_path,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            if os.path.exists(output_path):
                logger.info(f"Downloaded video: {video_id}")
                return output_path
            return None

        except Exception as e:
            logger.error(f"Error downloading video {video_id}: {e}")
            return None

    def extract_keyframes(
        self,
        video_path: str,
        output_dir: str | None = None,
        num_frames: int = 20,
    ) -> list[str]:
        """
        Extract keyframes from a video.

        Args:
            video_path: Path to video file
            output_dir: Directory for extracted frames
            num_frames: Target number of keyframes

        Returns:
            List of paths to extracted keyframe images
        """
        try:
            from katna.video import Video

            if output_dir is None:
                video_name = Path(video_path).stem
                output_dir = os.path.join(self.output_dir, f"{video_name}_frames")

            os.makedirs(output_dir, exist_ok=True)

            vd = Video()
            vd.extract_video_keyframes(
                no_of_frames=num_frames,
                file_path=video_path,
                writer=output_dir,
            )

            # Get list of extracted frames
            frames = sorted(
                [os.path.join(output_dir, f) for f in os.listdir(output_dir)
                 if f.endswith(('.jpg', '.png'))]
            )

            logger.info(f"Extracted {len(frames)} keyframes from {video_path}")
            return frames

        except Exception as e:
            logger.error(f"Error extracting keyframes from {video_path}: {e}")
            return []

    def process_video(
        self,
        video_id: str,
        num_frames: int = 20,
        cleanup: bool = True,
    ) -> list[str]:
        """
        Download video and extract keyframes.

        Args:
            video_id: YouTube video ID
            num_frames: Number of keyframes to extract
            cleanup: Remove downloaded video after extraction

        Returns:
            List of paths to extracted keyframe images
        """
        video_path = self.download_video(video_id)
        if not video_path:
            return []

        try:
            frames = self.extract_keyframes(video_path, num_frames=num_frames)
            return frames
        finally:
            if cleanup and video_path and os.path.exists(video_path):
                os.remove(video_path)
                logger.debug(f"Cleaned up video file: {video_path}")

    def match_frames_to_transcript(
        self,
        frames: list[str],
        transcript_segments: list[dict],
        video_duration_seconds: float,
    ) -> list[dict]:
        """
        Match extracted keyframes to transcript segments.

        Args:
            frames: List of keyframe paths (named by timestamp)
            transcript_segments: Transcript with start times
            video_duration_seconds: Total video duration

        Returns:
            List of dicts with frame path and matched transcript text
        """
        if not frames or not transcript_segments:
            return []

        # Estimate frame timestamps based on even distribution
        frame_interval = video_duration_seconds / len(frames)

        matched = []
        for i, frame_path in enumerate(frames):
            frame_time = i * frame_interval

            # Find closest transcript segment
            closest_segment = min(
                transcript_segments,
                key=lambda s: abs(s["start"] - frame_time)
            )

            matched.append({
                "frame_path": frame_path,
                "frame_time": frame_time,
                "transcript_text": closest_segment["text"],
                "transcript_start": closest_segment["start"],
            })

        return matched

    def compute_image_hash(self, image_path: str) -> str | None:
        """
        Compute perceptual hash of an image for similarity comparison.

        Uses average hash (aHash) which is fast and works well for slides.

        Args:
            image_path: Path to image file

        Returns:
            Hex string hash or None if failed
        """
        try:
            import imagehash
            from PIL import Image

            img = Image.open(image_path)
            # Use average hash - good balance of speed and accuracy for slides
            hash_value = imagehash.average_hash(img, hash_size=16)
            return str(hash_value)

        except Exception as e:
            logger.warning(f"Error computing hash for {image_path}: {e}")
            return None

    def compute_hash_similarity(self, hash1: str, hash2: str) -> float:
        """
        Compute similarity between two image hashes.

        Args:
            hash1: First hash string
            hash2: Second hash string

        Returns:
            Similarity score between 0.0 (different) and 1.0 (identical)
        """
        try:
            import imagehash

            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)

            # Hamming distance - number of different bits
            distance = h1 - h2

            # Convert to similarity (max distance for 16x16 hash = 256)
            max_distance = 16 * 16  # hash_size squared
            similarity = 1.0 - (distance / max_distance)

            return similarity

        except Exception as e:
            logger.warning(f"Error computing similarity: {e}")
            return 0.0

    def deduplicate_slides(
        self,
        frames: list[str],
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        video_duration_seconds: float | None = None,
    ) -> list[SlideFrame]:
        """
        Remove duplicate slide frames, keeping one representative per unique slide.

        Uses perceptual hashing to detect similar frames. When consecutive frames
        are similar (same slide displayed), only the first frame is kept.

        Args:
            frames: List of frame paths (should be sorted by timestamp)
            similarity_threshold: Minimum similarity (0-1) to consider frames as same slide
            video_duration_seconds: Optional video duration for timestamp estimation

        Returns:
            List of SlideFrame objects with unique slides only
        """
        if not frames:
            return []

        # Compute hashes for all frames
        frame_hashes: list[tuple[str, str | None]] = []
        for frame_path in frames:
            hash_value = self.compute_image_hash(frame_path)
            frame_hashes.append((frame_path, hash_value))

        # Estimate timestamps
        if video_duration_seconds:
            frame_interval = video_duration_seconds / len(frames)
        else:
            frame_interval = 1.0  # Default 1 second if duration unknown

        # Deduplicate by comparing consecutive frames
        unique_slides: list[SlideFrame] = []
        current_slide_hash: str | None = None

        for i, (frame_path, hash_value) in enumerate(frame_hashes):
            timestamp = i * frame_interval

            if hash_value is None:
                # Can't compare, keep the frame
                unique_slides.append(SlideFrame(
                    path=frame_path,
                    timestamp=timestamp,
                    hash_value="unknown",
                    is_representative=True,
                ))
                continue

            if current_slide_hash is None:
                # First frame, always keep
                current_slide_hash = hash_value
                unique_slides.append(SlideFrame(
                    path=frame_path,
                    timestamp=timestamp,
                    hash_value=hash_value,
                    is_representative=True,
                ))
                continue

            # Compare with current slide
            similarity = self.compute_hash_similarity(current_slide_hash, hash_value)

            if similarity < similarity_threshold:
                # Different slide detected, keep this frame
                current_slide_hash = hash_value
                unique_slides.append(SlideFrame(
                    path=frame_path,
                    timestamp=timestamp,
                    hash_value=hash_value,
                    is_representative=True,
                ))
                logger.debug(
                    f"New slide at {timestamp:.1f}s (similarity={similarity:.2f})"
                )
            else:
                # Same slide, skip this frame
                logger.debug(
                    f"Skipping duplicate at {timestamp:.1f}s (similarity={similarity:.2f})"
                )

        logger.info(
            f"Slide deduplication: {len(frames)} frames -> {len(unique_slides)} unique slides"
        )
        return unique_slides

    def extract_unique_slides(
        self,
        video_path: str,
        output_dir: str | None = None,
        num_frames: int = 50,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        video_duration_seconds: float | None = None,
    ) -> list[SlideFrame]:
        """
        Extract keyframes and deduplicate to get unique slides only.

        This is the main method for slide extraction - it extracts many frames
        then deduplicates to find distinct slides.

        Args:
            video_path: Path to video file
            output_dir: Directory for extracted frames
            num_frames: Number of frames to initially extract (before dedup)
            similarity_threshold: Threshold for considering frames as same slide
            video_duration_seconds: Video duration for timestamp calculation

        Returns:
            List of SlideFrame objects representing unique slides
        """
        # Extract more frames than needed, then deduplicate
        frames = self.extract_keyframes(
            video_path=video_path,
            output_dir=output_dir,
            num_frames=num_frames,
        )

        if not frames:
            return []

        # Deduplicate to get unique slides
        unique_slides = self.deduplicate_slides(
            frames=frames,
            similarity_threshold=similarity_threshold,
            video_duration_seconds=video_duration_seconds,
        )

        # Optionally clean up duplicate frame files
        unique_paths = {slide.path for slide in unique_slides}
        for frame_path in frames:
            if frame_path not in unique_paths:
                try:
                    os.remove(frame_path)
                except OSError:
                    pass

        return unique_slides
```

#### Step 4.2: Integrate Keyframes with Ingestion

Update `YouTubeIngestionService.ingest_playlist()` to optionally extract keyframes:

```python
# In ingest_playlist method, after getting transcript:
if settings.youtube_keyframe_extraction:
    from src.ingestion.youtube_keyframes import KeyframeExtractor

    extractor = KeyframeExtractor()

    # Download video temporarily
    video_path = extractor.download_video(video["video_id"])

    if video_path:
        try:
            # Get video duration for timestamp calculation
            video_info = self.client.get_video_details(video["video_id"])
            duration = video_info.get("duration_seconds", 600)

            # Extract unique slides (with deduplication)
            unique_slides = extractor.extract_unique_slides(
                video_path=video_path,
                num_frames=50,  # Extract many, then deduplicate
                similarity_threshold=0.85,  # 85% similar = same slide
                video_duration_seconds=duration,
            )

            if unique_slides:
                # Match slides to transcript segments
                slide_data = []
                for slide in unique_slides:
                    # Find transcript at this timestamp
                    closest_segment = min(
                        segments,
                        key=lambda s: abs(s["start"] - slide.timestamp)
                    )

                    slide_data.append({
                        "frame_path": slide.path,
                        "timestamp": slide.timestamp,
                        "timestamp_url": f"https://youtube.com/watch?v={video['video_id']}&t={int(slide.timestamp)}",
                        "transcript_text": closest_segment["text"],
                        "hash": slide.hash_value,
                    })

                transcript_metadata["slides"] = slide_data
                transcript_metadata["slide_count"] = len(unique_slides)
                logger.info(f"Extracted {len(unique_slides)} unique slides")

        finally:
            # Clean up downloaded video
            if os.path.exists(video_path):
                os.remove(video_path)
```

---

### Phase 5: Database Migration

#### Step 5.1: Create Alembic Migration

```bash
alembic revision --autogenerate -m "Add YouTube source type"
```

The migration should:
1. Add `YOUTUBE` to `NewsletterSource` enum
2. No schema changes needed (existing columns support YouTube data)

---

### Phase 6: Testing

#### Step 6.1: Unit Tests

**File**: `tests/test_ingestion/test_youtube.py`

```python
"""Tests for YouTube ingestion."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.ingestion.youtube import YouTubeClient, YouTubeIngestionService
from src.models.newsletter import NewsletterSource


class TestYouTubeClient:
    """Tests for YouTubeClient."""

    @patch("src.ingestion.youtube.build")
    @patch("src.ingestion.youtube.Credentials")
    def test_authenticate_api_key(self, mock_creds, mock_build):
        """Test API key authentication."""
        with patch("src.ingestion.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "test-api-key"
            client = YouTubeClient(use_oauth=False)
            assert client.service is not None

    def test_get_transcript_success(self):
        """Test successful transcript retrieval."""
        with patch("src.ingestion.youtube.YouTubeTranscriptApi") as mock_api:
            mock_transcript = Mock()
            mock_transcript.fetch.return_value = [
                {"text": "Hello", "start": 0.0, "duration": 1.5},
                {"text": "World", "start": 1.5, "duration": 1.5},
            ]
            mock_list = Mock()
            mock_list.find_transcript.return_value = mock_transcript
            mock_api.list_transcripts.return_value = mock_list

            client = YouTubeClient.__new__(YouTubeClient)
            client.service = Mock()

            result = client.get_transcript("test-video-id")

            assert result is not None
            full_text, segments = result
            assert "Hello" in full_text
            assert len(segments) == 2


class TestYouTubeIngestionService:
    """Tests for YouTubeIngestionService."""

    @pytest.fixture
    def mock_service(self):
        """Create mock ingestion service."""
        with patch.object(YouTubeIngestionService, "__init__", lambda x, **k: None):
            service = YouTubeIngestionService()
            service.client = Mock()
            return service

    def test_ingest_playlist_empty(self, mock_service):
        """Test ingestion with empty playlist."""
        mock_service.client.get_playlist_videos.return_value = []

        count = mock_service.ingest_playlist("PLtest")

        assert count == 0
```

#### Step 6.2: Integration Tests

```python
"""Integration tests for YouTube ingestion."""

import pytest
from src.ingestion.youtube import YouTubeIngestionService


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("YOUTUBE_API_KEY"),
    reason="YOUTUBE_API_KEY not set"
)
class TestYouTubeIntegration:
    """Integration tests requiring real API access."""

    def test_public_playlist_ingestion(self):
        """Test ingesting a public playlist."""
        # Use a well-known public playlist (e.g., Google Developers)
        service = YouTubeIngestionService(use_oauth=False)

        count = service.ingest_playlist(
            playlist_id="PLIivdWyY5sqJxnwJhe3etaK57n6guoGAy",  # Google Cloud Tech
            max_videos=2,
        )

        assert count >= 0  # May be 0 if transcripts disabled
```

---

## Configuration Summary

### Environment Variables

```bash
# Required for private playlists
YOUTUBE_CREDENTIALS_FILE=youtube_credentials.json
YOUTUBE_TOKEN_FILE=youtube_token.json

# Required for public playlists (without OAuth)
YOUTUBE_API_KEY=AIza...

# Playlist configuration
YOUTUBE_PLAYLISTS=PLxxx,PLyyy,PLzzz

# Optional: Keyframe extraction
YOUTUBE_KEYFRAME_EXTRACTION=false
YOUTUBE_TEMP_DIR=/tmp/youtube_downloads
```

### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials (for private playlists)
   - Application type: Desktop app
   - Download JSON as `youtube_credentials.json`
5. Or create API key (for public playlists only)

---

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `src/models/newsletter.py` | UPDATE | Add `YOUTUBE` to `NewsletterSource` |
| `src/models/youtube.py` | CREATE | YouTube-specific models with timestamp support |
| `src/utils/youtube_links.py` | CREATE | URL generation and parsing utilities |
| `src/config/settings.py` | UPDATE | Add YouTube configuration |
| `src/ingestion/youtube.py` | CREATE | YouTube client and ingestion service |
| `src/ingestion/youtube_keyframes.py` | CREATE | Keyframe extraction (optional) |
| `tests/test_ingestion/test_youtube.py` | CREATE | Unit and integration tests |
| `pyproject.toml` | UPDATE | Add dependencies |
| `alembic/versions/xxx.py` | CREATE | Database migration |

---

## Dependencies

```toml
[project.dependencies]
youtube-transcript-api = ">=0.6.0"
# These are likely already present:
google-api-python-client = ">=2.100.0"
google-auth-oauthlib = ">=1.0.0"

[project.optional-dependencies]
youtube-keyframes = [
    "yt-dlp>=2024.1.0",
    "katna>=0.10.0",
    "imagehash>=4.3.0",  # Perceptual hashing for slide deduplication
    "Pillow>=10.0.0",    # Image processing (likely already present)
]
```

---

## Implementation Order

1. **Step 1**: Add `YOUTUBE` source type to model
2. **Step 2**: Add configuration settings
3. **Step 3**: Install dependencies
4. **Step 4**: Implement `YouTubeClient`
5. **Step 5**: Implement `YouTubeIngestionService`
6. **Step 6**: Add CLI entry point
7. **Step 7**: Create database migration
8. **Step 8**: Write tests
9. **Step 9** (Optional): Implement keyframe extraction

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Transcripts not available for all videos | Log warning, skip video, continue with others |
| API quota limits | Use `youtube-transcript-api` (no quota) for transcripts, only use Data API for playlist access |
| Private playlist OAuth complexity | Reuse Gmail OAuth pattern, clear documentation |
| Large video downloads for keyframes | Use lowest quality, cleanup after extraction, make optional |
| Keyframe extraction dependencies (ffmpeg) | Document system requirements, make feature optional |

---

## Integration with Summarization Pipeline

### Timestamp-Aware Summarization

The summarization processor should be enhanced to:

1. **Extract notable quotes with timestamps**: When the LLM identifies key quotes, include the timestamp
2. **Store TimestampedQuote objects**: Save references for digest generation
3. **Generate deep-links**: Include timestamp URLs in the summary output

**Example Summary Output Structure**:
```python
class YouTubeSummary(BaseModel):
    """Extended summary for YouTube content."""

    # Standard fields
    executive_summary: str
    key_themes: list[str]

    # YouTube-specific fields
    notable_quotes: list[TimestampedQuote]  # Quotes with timestamps
    key_moments: list[dict]  # {timestamp, description, url}
    chapters: list[dict] | None  # If video has chapters
```

### Digest Integration

When creating digests that include YouTube content:

```markdown
## Key Insights from Video Content

### "The Future of AI Agents" - Anthropic (12:34)

> "The key insight is that agents need to be able to reason about their own capabilities..."
> — [Watch @ 5:23](https://youtube.com/watch?v=xyz&t=323)

**Key Moments:**
- [2:15](https://youtube.com/watch?v=xyz&t=135) - Introduction to agent architectures
- [8:45](https://youtube.com/watch?v=xyz&t=525) - Tool use patterns
- [15:30](https://youtube.com/watch?v=xyz&t=930) - Future directions

[▶️ Watch Full Video](https://youtube.com/watch?v=xyz)
```

### Embedded Player Support (Future)

The `build_embed_html()` utility enables future web UI features:

```html
<!-- Embed with specific timestamp range -->
<iframe src="https://youtube.com/embed/VIDEO_ID?start=323&end=400" ...></iframe>
```

This allows:
- Inline video clips in web-based digests
- "Play this section" buttons next to quotes
- Video highlights carousel

---

## Future Enhancements

1. **Channel ingestion**: Ingest all videos from a channel (not just playlists)
2. **Watch Later / Liked**: Support special playlists
3. **Auto-captions quality**: Prefer manual captions, flag auto-generated
4. **Slide OCR**: Use vision models to extract text from keyframes
5. **Chapter extraction**: Parse YouTube chapter markers for navigation
6. **Transcript search API**: Search across all ingested transcripts with timestamp results
7. **Video clips API**: Generate embed codes for specific timestamp ranges
8. **Speaker diarization**: Identify different speakers in transcripts (future ML feature)
