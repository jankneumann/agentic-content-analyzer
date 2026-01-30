"""Podcast ingestion with transcript-first strategy.

Implements a 3-tier approach to extracting podcast episode transcripts:
1. Feed-embedded: Extract from <content:encoded>, <description>, <itunes:summary>
2. Linked page: Detect transcript/show-notes URLs and fetch via HTTP
3. Audio fallback: Download audio and transcribe via STT (gated by transcribe=true)
"""

from __future__ import annotations

import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import feedparser
import httpx

from src.config import settings
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.config.sources import PodcastSource

logger = get_logger(__name__)

# Minimum character count to consider feed-embedded text a valid transcript
MIN_TRANSCRIPT_LENGTH = 500

# Patterns for detecting transcript links in show notes
TRANSCRIPT_URL_PATTERNS = [
    r"https?://[^\s\"'>]+/transcript[^\s\"'>]*",
    r"https?://[^\s\"'>]+/show-notes[^\s\"'>]*",
    r"https?://[^\s\"'>]+/episodes?/[^\s\"'>]+/transcript[^\s\"'>]*",
]


class PodcastClient:
    """Client for fetching and parsing podcast RSS feeds."""

    def fetch_feed(self, feed_url: str, max_entries: int = 10) -> list[dict[str, Any]]:
        """Fetch and parse a podcast RSS feed.

        Args:
            feed_url: RSS feed URL
            max_entries: Maximum episodes to return

        Returns:
            List of episode metadata dicts with keys: guid, title, link,
            published_date, description, content_encoded, itunes_summary,
            audio_url, duration, author, feed_title
        """
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse podcast feed: {feed_url}")
            return []

        feed_title = feed.feed.get("title", "")
        episodes = []

        for entry in feed.entries[:max_entries]:
            # Extract audio URL from enclosures
            audio_url = None
            for enclosure in entry.get("enclosures", []):
                if enclosure.get("type", "").startswith("audio/"):
                    audio_url = enclosure.get("href")
                    break

            # Parse published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                except (TypeError, ValueError):
                    pass

            # Extract content fields
            content_encoded = ""
            for content_item in entry.get("content", []):
                if content_item.get("type") in ("text/html", "text/plain"):
                    content_encoded = content_item.get("value", "")
                    break

            episodes.append(
                {
                    "guid": entry.get("id", entry.get("link", "")),
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published_date": published,
                    "description": entry.get("summary", ""),
                    "content_encoded": content_encoded,
                    "itunes_summary": entry.get("itunes_summary", ""),
                    "audio_url": audio_url,
                    "duration": entry.get("itunes_duration", ""),
                    "author": entry.get("author", ""),
                    "feed_title": feed_title,
                }
            )

        return episodes

    def extract_transcript_from_feed(self, episode: dict[str, Any]) -> str | None:
        """Tier 1: Extract transcript from feed-embedded content.

        Checks content_encoded, description, and itunes_summary in order.
        Returns the text if it's >= MIN_TRANSCRIPT_LENGTH characters.
        """
        for field in ("content_encoded", "description", "itunes_summary"):
            text = episode.get(field, "")
            if text and len(text) >= MIN_TRANSCRIPT_LENGTH:
                return text
        return None

    def extract_transcript_from_url(self, episode: dict[str, Any]) -> str | None:
        """Tier 2: Detect and fetch transcript from linked page.

        Scans show notes for transcript/show-notes URLs, then fetches
        the page content via HTTP.
        """
        # Search all text fields for transcript URLs
        text_to_search = " ".join(
            [
                episode.get("description", ""),
                episode.get("content_encoded", ""),
                episode.get("link", ""),
            ]
        )

        for pattern in TRANSCRIPT_URL_PATTERNS:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                url = match.group(0)
                try:
                    with httpx.Client(timeout=30, follow_redirects=True) as client:
                        response = client.get(url)
                        response.raise_for_status()

                        # Basic HTML stripping -- extract text content
                        from src.parsers.html_markdown import convert_html_to_markdown

                        text = convert_html_to_markdown(response.text)
                        if text and len(text) >= MIN_TRANSCRIPT_LENGTH:
                            logger.info(f"Found transcript at: {url}")
                            return text
                except Exception as e:
                    logger.debug(f"Failed to fetch transcript from {url}: {e}")
                    continue

        return None


class PodcastContentIngestionService:
    """Service for ingesting podcast episodes into the unified Content model.

    Uses a 3-tier transcript extraction strategy:
    1. Feed-embedded text (content:encoded, description, itunes:summary)
    2. Linked transcript page (detect URLs in show notes)
    3. Audio transcription (download + STT, gated by transcribe=true)
    """

    def __init__(self) -> None:
        """Initialize podcast content ingestion service."""
        self.client = PodcastClient()

    def ingest_feed(
        self,
        feed_url: str,
        max_entries: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
        source_name: str | None = None,
        source_tags: list[str] | None = None,
        transcribe: bool = True,
        stt_provider: str = "openai",
        languages: list[str] | None = None,
    ) -> int:
        """Ingest episodes from a single podcast feed.

        For each episode, tries the 3-tier transcript strategy:
        1. Feed-embedded transcript (if >= 500 chars)
        2. Linked transcript page
        3. Audio transcription (if transcribe=True and audio_url available)

        Returns:
            Number of episodes ingested
        """
        episodes = self.client.fetch_feed(feed_url, max_entries=max_entries)

        if not episodes:
            logger.info(f"No episodes found in podcast feed: {feed_url}")
            return 0

        count = 0
        with get_db() as db:
            for episode in episodes:
                guid = episode["guid"]
                source_id = f"podcast:{guid}"

                # Date filter
                if (
                    after_date
                    and episode.get("published_date")
                    and episode["published_date"] < after_date
                ):
                    continue

                # Dedup check
                if not force_reprocess:
                    existing = db.query(Content).filter(Content.source_id == source_id).first()
                    if existing:
                        logger.debug(f"Skipping existing episode: {episode['title']}")
                        continue

                # 3-tier transcript extraction
                transcript_text = None
                raw_format = None

                # Tier 1: Feed-embedded
                transcript_text = self.client.extract_transcript_from_feed(episode)
                if transcript_text:
                    raw_format = "feed_transcript"
                    logger.info(f"Tier 1 (feed): Transcript found for '{episode['title']}'")

                # Tier 2: Linked page
                if not transcript_text:
                    transcript_text = self.client.extract_transcript_from_url(episode)
                    if transcript_text:
                        raw_format = "linked_transcript"
                        logger.info(f"Tier 2 (link): Transcript found for '{episode['title']}'")

                # Tier 3: Audio transcription (gated)
                if not transcript_text and transcribe and episode.get("audio_url"):
                    transcript_text = self._transcribe_audio(
                        audio_url=episode["audio_url"],
                        stt_provider=stt_provider,
                        languages=languages,
                    )
                    if transcript_text:
                        raw_format = "audio_transcript"
                        logger.info(
                            f"Tier 3 (audio): Transcript generated for '{episode['title']}'"
                        )

                if not transcript_text:
                    logger.info(f"No transcript available for episode: {episode['title']}")
                    continue

                # Convert to markdown
                markdown_content = self._to_markdown(episode, transcript_text)
                content_hash = generate_markdown_hash(markdown_content)

                # Build metadata
                metadata: dict[str, Any] = {
                    "guid": guid,
                    "feed_url": feed_url,
                    "audio_url": episode.get("audio_url"),
                    "duration": episode.get("duration"),
                    "raw_format": raw_format,
                    "feed_title": episode.get("feed_title"),
                }
                if source_name:
                    metadata["source_name"] = source_name
                if source_tags:
                    metadata["source_tags"] = source_tags

                try:
                    content = Content(
                        source_type=ContentSource.PODCAST,
                        source_id=source_id,
                        title=episode.get("title", f"Episode {guid}"),
                        source_url=episode.get("link"),
                        raw_content=transcript_text,
                        raw_format=raw_format,
                        markdown_content=markdown_content,
                        content_hash=content_hash,
                        parser_used="podcast_rss",
                        status=ContentStatus.PARSED,
                        published_date=episode.get("published_date"),
                        metadata_json=metadata,
                    )
                    db.add(content)
                    db.commit()
                    count += 1
                except Exception as e:
                    logger.error(f"Error creating content for episode '{episode['title']}': {e}")
                    db.rollback()
                    continue

        return count

    def ingest_all_feeds(
        self,
        sources: list[PodcastSource] | None = None,
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """Ingest episodes from multiple podcast feeds.

        Source resolution:
        1. sources parameter (PodcastSource objects)
        2. SourcesConfig (YAML files)
        """
        resolved_sources: list[PodcastSource] = []

        if sources is not None:
            resolved_sources = [s for s in sources if s.enabled]
        else:
            config = settings.get_sources_config()
            resolved_sources = config.get_podcast_sources()

        if not resolved_sources:
            logger.info("No podcast sources configured")
            return 0

        total = 0
        for source in resolved_sources:
            try:
                max_entries = source.max_entries or max_entries_per_feed
                count = self.ingest_feed(
                    feed_url=source.url,
                    max_entries=max_entries,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                    source_name=source.name,
                    source_tags=source.tags if source.tags else None,
                    transcribe=source.transcribe,
                    stt_provider=source.stt_provider,
                    languages=source.languages if source.languages else None,
                )
                total += count
            except Exception as e:
                logger.error(f"Error ingesting podcast feed {source.name or source.url}: {e}")
                continue

        return total

    def _to_markdown(self, episode: dict[str, Any], transcript_text: str) -> str:
        """Convert episode transcript to markdown format."""
        lines = []

        # Title
        title = episode.get("title", "Untitled Episode")
        lines.append(f"# {title}")
        lines.append("")

        # Metadata
        if episode.get("feed_title"):
            lines.append(f"**Podcast:** {episode['feed_title']}")
        if episode.get("author"):
            lines.append(f"**Host:** {episode['author']}")
        if episode.get("published_date"):
            lines.append(f"**Published:** {episode['published_date'].strftime('%Y-%m-%d')}")
        if episode.get("link"):
            lines.append(f"**Episode:** [{title}]({episode['link']})")
        if episode.get("duration"):
            lines.append(f"**Duration:** {episode['duration']}")
        lines.append("")

        # Transcript
        lines.append("## Transcript")
        lines.append("")
        lines.append(transcript_text)

        return "\n".join(lines)

    # Providers that have a working transcription implementation
    SUPPORTED_STT_PROVIDERS: ClassVar[set[str]] = {"openai"}

    def _transcribe_audio(
        self,
        audio_url: str,
        stt_provider: str = "openai",
        languages: list[str] | None = None,
    ) -> str | None:
        """Tier 3: Download audio and transcribe via STT.

        This is gated by the ``transcribe=True`` flag on the source config.
        Downloads audio to a temp file, then transcribes via the configured STT provider.

        Returns:
            Transcribed text or None if transcription fails.
        """
        # Validate provider before downloading audio to avoid wasted bandwidth
        if stt_provider not in self.SUPPORTED_STT_PROVIDERS:
            logger.error(
                f"STT provider '{stt_provider}' is not yet implemented. "
                f"Supported providers: {', '.join(sorted(self.SUPPORTED_STT_PROVIDERS))}. "
                f"Skipping audio transcription for: {audio_url}"
            )
            return None

        max_duration = settings.podcast_max_duration_minutes
        temp_dir = settings.podcast_temp_dir
        temp_path: str | None = None

        try:
            # Download audio to temp file
            Path(temp_dir).mkdir(parents=True, exist_ok=True)

            with httpx.Client(timeout=300, follow_redirects=True) as http_client:
                response = http_client.get(audio_url)
                response.raise_for_status()

                # Check content length (rough duration estimate: ~1MB per minute for mp3)
                content_length = len(response.content)
                estimated_minutes = content_length / (1024 * 1024)
                if estimated_minutes > max_duration:
                    logger.warning(
                        f"Audio too long (~{estimated_minutes:.0f} min, "
                        f"max {max_duration} min): {audio_url}"
                    )
                    return None

                # Write to temp file
                suffix = ".mp3"
                if "audio/mp4" in response.headers.get("content-type", ""):
                    suffix = ".m4a"
                elif "audio/wav" in response.headers.get("content-type", ""):
                    suffix = ".wav"

                with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=suffix, delete=False) as f:
                    f.write(response.content)
                    temp_path = f.name

            # Transcribe using configured provider
            return self._transcribe_openai(temp_path, languages)

        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return None
        finally:
            # Cleanup temp file
            if temp_path is not None:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def _transcribe_openai(self, audio_path: str, languages: list[str] | None = None) -> str | None:
        """Transcribe audio using OpenAI Whisper API.

        Args:
            audio_path: Path to local audio file
            languages: Preferred languages (first is used as hint)

        Returns:
            Transcribed text or None
        """
        try:
            from openai import OpenAI

            client = OpenAI()
            language = languages[0] if languages else None

            with open(audio_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                )

            return response.text
        except ImportError:
            logger.error("OpenAI package not installed. Install with: pip install openai")
            return None
        except Exception as e:
            logger.error(f"OpenAI transcription error: {e}")
            return None
