"""YouTube parser for transcript extraction with timestamp support."""

import logging
import time
from pathlib import Path
from typing import BinaryIO, ClassVar

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata
from src.models.youtube import TranscriptSegment, YouTubeTranscript
from src.parsers.base import DocumentParser
from src.utils.youtube_links import extract_video_id, is_youtube_url

logger = logging.getLogger(__name__)


class YouTubeParser(DocumentParser):
    """Specialized parser for YouTube video transcripts.

    Unlike MarkItDown's thin wrapper, this parser:
    - Directly uses youtube-transcript-api for better control
    - Preserves timestamp information for deep-linking
    - Generates markdown with clickable timestamp links
    - Supports multiple language preferences
    - Provides structured transcript segments for downstream processing

    Best for:
    - YouTube video transcripts
    - Content requiring timestamp-based navigation
    - Videos needing quote extraction with time references
    """

    supported_formats: ClassVar[set[str]] = {"youtube"}
    fallback_formats: ClassVar[set[str]] = set()

    # Default language preferences (in order of priority)
    DEFAULT_LANGUAGES: ClassVar[list[str]] = ["en", "en-US", "en-GB"]

    def __init__(self, languages: list[str] | None = None) -> None:
        """Initialize the YouTube parser.

        Args:
            languages: Preferred transcript languages in order of priority.
                      Defaults to English variants.
        """
        self.languages = languages or self.DEFAULT_LANGUAGES

    @property
    def name(self) -> str:
        """Parser identifier."""
        return "youtube"

    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> DocumentContent:
        """Parse YouTube video and extract transcript.

        Args:
            source: YouTube URL or video ID
            format_hint: Optional format override (ignored for YouTube)

        Returns:
            DocumentContent with timestamped markdown transcript
        """
        start_time = time.time()
        warnings: list[str] = []

        # Extract video ID from URL or use directly
        source_str = str(source)
        video_id = extract_video_id(source_str)
        if not video_id:
            # Assume it's a direct video ID
            video_id = source_str.strip()
            if len(video_id) != 11:
                raise ValueError(f"Invalid YouTube video ID or URL: {source_str}")

        try:
            # Fetch transcript using youtube-transcript-api
            transcript_data = self._fetch_transcript(video_id)

            if transcript_data is None:
                raise ValueError(f"No transcript available for video: {video_id}")

            segments, is_auto_generated, language = transcript_data

            # Build YouTubeTranscript model
            youtube_transcript = YouTubeTranscript(
                video_id=video_id,
                title=f"YouTube Video {video_id}",  # Title would require API call
                segments=segments,
                language=language,
                is_auto_generated=is_auto_generated,
            )

            # Generate markdown with timestamps
            markdown_content = youtube_transcript.to_markdown()

            # Extract links (the video URL itself)
            links = [youtube_transcript.video_url]

            processing_time = int((time.time() - start_time) * 1000)

            return DocumentContent(
                markdown_content=markdown_content,
                source_path=source_str,
                source_format=DocumentFormat.YOUTUBE,
                parser_used=self.name,
                metadata=DocumentMetadata(
                    title=youtube_transcript.title,
                    language=language,
                ),
                links=links,
                processing_time_ms=processing_time,
                warnings=warnings,
            )

        except (NoTranscriptFound, TranscriptsDisabled) as e:
            logger.warning(f"Transcript not available for {video_id}: {e}")
            raise ValueError(f"Transcript not available: {e}") from e
        except Exception as e:
            logger.error(f"YouTube parsing failed for {video_id}: {e}")
            raise

    def can_parse(
        self,
        source: str | Path,
        format_hint: str | None = None,
    ) -> bool:
        """Check if this parser can handle the given source.

        Args:
            source: File path or URL
            format_hint: Optional format override

        Returns:
            True if this is a YouTube URL or video ID
        """
        if format_hint == "youtube":
            return True

        source_str = str(source)
        return is_youtube_url(source_str)

    def _fetch_transcript(self, video_id: str) -> tuple[list[TranscriptSegment], bool, str] | None:
        """Fetch transcript from YouTube.

        Args:
            video_id: YouTube video ID

        Returns:
            Tuple of (segments, is_auto_generated, language) or None
        """
        try:
            # Try to get transcript in preferred languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)  # type: ignore[attr-defined]

            # First try manually created transcripts
            transcript = None
            is_auto_generated = False

            try:
                transcript = transcript_list.find_manually_created_transcript(self.languages)
            except NoTranscriptFound:
                # Fall back to auto-generated
                try:
                    transcript = transcript_list.find_generated_transcript(self.languages)
                    is_auto_generated = True
                except NoTranscriptFound:
                    # Try any available transcript
                    for t in transcript_list:
                        transcript = t
                        is_auto_generated = t.is_generated
                        break

            if transcript is None:
                return None

            # Fetch the actual transcript data
            raw_transcript = transcript.fetch()
            language = transcript.language_code

            # Convert to our segment model
            segments = [
                TranscriptSegment(
                    text=entry["text"],
                    start=entry["start"],
                    duration=entry["duration"],
                    is_generated=is_auto_generated,
                )
                for entry in raw_transcript
            ]

            return segments, is_auto_generated, language

        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            raise

    def get_transcript_with_metadata(self, source: str) -> YouTubeTranscript | None:
        """Get full YouTubeTranscript object for advanced usage.

        This method provides access to the structured transcript data
        including segments, timestamps, and search capabilities.

        Args:
            source: YouTube URL or video ID

        Returns:
            YouTubeTranscript object or None if unavailable
        """
        source_str = str(source)
        video_id = extract_video_id(source_str) or source_str.strip()

        if len(video_id) != 11:
            return None

        try:
            transcript_data = self._fetch_transcript(video_id)
            if transcript_data is None:
                return None

            segments, is_auto_generated, language = transcript_data

            return YouTubeTranscript(
                video_id=video_id,
                title=f"YouTube Video {video_id}",
                segments=segments,
                language=language,
                is_auto_generated=is_auto_generated,
            )
        except Exception:
            return None
