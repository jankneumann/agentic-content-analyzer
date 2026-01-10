"""YouTube transcript ingestion."""

import argparse
import os
from datetime import UTC, datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from src.config import settings
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.models.youtube import TranscriptSegment, YouTubeTranscript
from src.storage.database import get_db
from src.utils.content_hash import generate_content_hash
from src.utils.logging import get_logger

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
            use_oauth: If True, use OAuth for private playlist access.
                      If False, use API key for public playlists only.
        """
        self.service: Any = None
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

        self.service = build("youtube", "v3", credentials=creds)
        logger.info("YouTube API client initialized (OAuth)")

    def _authenticate_api_key(self) -> None:
        """Authenticate using API key (for public playlists only)."""
        api_key = settings.get_youtube_api_key()
        if not api_key:
            raise ValueError(
                "YOUTUBE_API_KEY or GOOGLE_API_KEY required for public playlist access"
            )

        self.service = build("youtube", "v3", developerKey=api_key)
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
            # Try to get transcript in preferred languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)  # type: ignore[attr-defined]

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

            # Fetch the transcript
            raw_segments = transcript.fetch()
            language = transcript.language_code

            # Convert to our segment model
            segments = [
                TranscriptSegment(
                    text=entry["text"],
                    start=entry["start"],
                    duration=entry["duration"],
                    is_generated=is_auto_generated,
                )
                for entry in raw_segments
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
        languages: list[str] | None = None,
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

                    # Check if already exists
                    existing = (
                        db.query(Newsletter).filter(Newsletter.source_id == source_id).first()
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

                    # Get full text for content hash
                    full_text = transcript.full_text

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
                    video_url = transcript.video_url

                    # Store transcript metadata as JSON
                    transcript_metadata = transcript.to_storage_dict()

                    # Optional: Extract keyframes for slide detection
                    if settings.youtube_keyframe_extraction:
                        transcript_metadata = self._extract_keyframes(
                            video_id=video["video_id"],
                            transcript=transcript,
                            transcript_metadata=transcript_metadata,
                        )

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
            playlist_ids: List of playlist IDs (uses config file if None)
            max_videos_per_playlist: Max videos per playlist
            after_date: Only process videos after this date
            force_reprocess: Reprocess existing videos

        Returns:
            Total number of transcripts ingested
        """
        if playlist_ids is None:
            # Load from config file
            playlists = settings.get_youtube_playlists()
            playlist_ids = [p["id"] for p in playlists if p["id"]]

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

    def _extract_keyframes(
        self,
        video_id: str,
        transcript: YouTubeTranscript,
        transcript_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Extract keyframes from a video and add to metadata.

        Args:
            video_id: YouTube video ID
            transcript: YouTubeTranscript object with segments
            transcript_metadata: Existing metadata dict to augment

        Returns:
            Updated transcript_metadata with keyframe data
        """
        try:
            from src.ingestion.youtube_keyframes import KeyframeExtractor

            extractor = KeyframeExtractor()

            # Check if ffmpeg is available
            if not extractor.is_available():
                logger.warning("Keyframe extraction skipped: ffmpeg not available")
                return transcript_metadata

            # Prepare transcript segments for matching
            segments = [
                {"text": seg.text, "start": seg.start, "duration": seg.duration}
                for seg in transcript.segments
            ]

            # Extract keyframes
            result = extractor.extract_keyframes_for_video(
                video_id=video_id,
                transcript_segments=segments,
            )

            if result.error:
                logger.warning(f"Keyframe extraction failed: {result.error}")
                return transcript_metadata

            if result.slides:
                # Build slide data for storage
                slide_data = []
                for slide in result.slides:
                    # Find closest transcript segment
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

                transcript_metadata["slides"] = slide_data
                transcript_metadata["slide_count"] = result.slide_count
                transcript_metadata["extraction_method"] = result.extraction_method

                logger.info(f"Added {result.slide_count} keyframes to metadata")

        except ImportError:
            logger.warning("Keyframe extraction skipped: dependencies not installed")
        except Exception as e:
            logger.error(f"Keyframe extraction error: {e}")

        return transcript_metadata


def main() -> None:
    """CLI entry point for YouTube ingestion."""
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
