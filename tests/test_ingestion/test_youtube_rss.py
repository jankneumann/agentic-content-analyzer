"""Tests for YouTube RSS feed ingestion.

Tests that YouTubeRSSIngestionService correctly parses RSS/Atom feeds,
extracts video IDs, fetches transcripts, deduplicates, and creates Content
records.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.config.sources import YouTubeRSSSource
from src.ingestion.youtube import YouTubeClient, YouTubeRSSIngestionService
from src.models.youtube import TranscriptSegment, YouTubeTranscript

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_init(self, use_oauth=True):
    """Mock YouTubeClient init that avoids real auth."""
    self.service = MagicMock()
    self.use_oauth = use_oauth
    self.oauth_available = False


def _mock_rss_init(self):
    """Mock YouTubeRSSIngestionService init that avoids real YouTubeClient."""
    self.client = MagicMock()


class FeedEntry:
    """Dict-like feedparser entry mock that supports .get() and attributes."""

    def __init__(self, data, published_parsed=None):
        self._data = data
        self.published_parsed = published_parsed or (2024, 6, 15, 12, 0, 0, 5, 167, 0)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getattr__(self, name):
        if name.startswith("_") or name == "published_parsed":
            raise AttributeError(name)
        return self._data.get(name)


def _make_feed_entry(video_id=None, title="Test Video", link=None, channel="Test Channel"):
    """Create a feedparser-like entry with optional yt_videoid."""
    data = {
        "title": title,
        "link": link or f"https://www.youtube.com/watch?v={video_id or 'fallback'}",
        "author": channel,
    }
    if video_id is not None:
        data["yt_videoid"] = video_id
    return FeedEntry(data)


def _make_mock_feed(entries):
    """Create a mock feedparser result with given entries."""
    feed = MagicMock()
    feed.bozo = False
    feed.entries = entries
    feed.feed.get = lambda key, default="": default
    return feed


# ---------------------------------------------------------------------------
# TestYouTubeRSSParsing
# ---------------------------------------------------------------------------


class TestYouTubeRSSParsing:
    """Tests for YouTubeRSSIngestionService._parse_feed()."""

    @patch.object(YouTubeRSSIngestionService, "__init__", _mock_rss_init)
    @patch("feedparser.parse")
    def test_parses_atom_feed_entries(self, mock_parse):
        """Parse feed with yt_videoid entries extracts video IDs and metadata."""
        entries = [
            _make_feed_entry(video_id="vid001", title="First Video", channel="Channel A"),
            _make_feed_entry(video_id="vid002", title="Second Video", channel="Channel B"),
        ]
        mock_parse.return_value = _make_mock_feed(entries)

        service = YouTubeRSSIngestionService()
        result = service._parse_feed("https://www.youtube.com/feeds/videos.xml?channel_id=UC123")

        assert len(result) == 2
        assert result[0]["video_id"] == "vid001"
        assert result[0]["title"] == "First Video"
        assert result[0]["channel_title"] == "Channel A"
        assert result[1]["video_id"] == "vid002"
        assert result[1]["title"] == "Second Video"
        mock_parse.assert_called_once()

    @patch.object(YouTubeRSSIngestionService, "__init__", _mock_rss_init)
    @patch("feedparser.parse")
    def test_extracts_video_id_from_link_fallback(self, mock_parse):
        """Entry without yt_videoid falls back to extracting from link URL."""
        entry = _make_feed_entry(
            video_id=None,
            title="Fallback Video",
            link="https://www.youtube.com/watch?v=abc123",
        )
        mock_parse.return_value = _make_mock_feed([entry])

        service = YouTubeRSSIngestionService()
        result = service._parse_feed("https://example.com/feed")

        assert len(result) == 1
        assert result[0]["video_id"] == "abc123"
        assert result[0]["title"] == "Fallback Video"

    @patch.object(YouTubeRSSIngestionService, "__init__", _mock_rss_init)
    @patch("feedparser.parse")
    def test_skips_entries_without_video_id(self, mock_parse):
        """Entries with no video ID in yt_videoid or link are skipped."""
        entry = _make_feed_entry(
            video_id=None,
            title="No ID Video",
            link="https://www.youtube.com/channel/UC123",
        )
        mock_parse.return_value = _make_mock_feed([entry])

        service = YouTubeRSSIngestionService()
        result = service._parse_feed("https://example.com/feed")

        assert len(result) == 0

    @patch.object(YouTubeRSSIngestionService, "__init__", _mock_rss_init)
    @patch("feedparser.parse")
    def test_respects_max_entries(self, mock_parse):
        """Feed with 5 entries but max_entries=2 returns only 2."""
        entries = [_make_feed_entry(video_id=f"vid{i}", title=f"Video {i}") for i in range(5)]
        mock_parse.return_value = _make_mock_feed(entries)

        service = YouTubeRSSIngestionService()
        result = service._parse_feed("https://example.com/feed", max_entries=2)

        assert len(result) == 2
        assert result[0]["video_id"] == "vid0"
        assert result[1]["video_id"] == "vid1"


# ---------------------------------------------------------------------------
# TestYouTubeRSSIngestion
# ---------------------------------------------------------------------------


class TestYouTubeRSSIngestion:
    """Tests for YouTubeRSSIngestionService.ingest_feed()."""

    @patch("src.ingestion.youtube.get_db")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "_parse_feed")
    def test_ingests_video_with_transcript(self, mock_parse_feed, mock_get_db):
        """Video with transcript creates a Content record."""
        mock_parse_feed.return_value = [
            {
                "video_id": "abc123",
                "title": "Test Video",
                "channel_title": "Test Channel",
                "published_date": datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
                "link": "https://www.youtube.com/watch?v=abc123",
            },
        ]

        mock_transcript = YouTubeTranscript(
            video_id="abc123",
            title="Test Video",
            channel_title="Test Channel",
            segments=[TranscriptSegment(text="Hello world", start=0.0, duration=5.0)],
        )

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        # No existing record (dedup check returns None)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = YouTubeRSSIngestionService()
        service.client.get_transcript = MagicMock(return_value=mock_transcript)

        count = service.ingest_feed("https://example.com/feed")

        assert count == 1
        mock_db.add.assert_called_once()
        added_content = mock_db.add.call_args[0][0]
        assert added_content.source_id == "youtube:abc123"
        assert added_content.title == "Test Video"

    @patch("src.ingestion.youtube.get_db")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "_parse_feed")
    def test_skips_video_without_transcript(self, mock_parse_feed, mock_get_db):
        """Video with no transcript is skipped."""
        mock_parse_feed.return_value = [
            {
                "video_id": "no_transcript",
                "title": "No Transcript Video",
                "channel_title": "Channel",
                "published_date": datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
                "link": "https://www.youtube.com/watch?v=no_transcript",
            },
        ]

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = YouTubeRSSIngestionService()
        service.client.get_transcript = MagicMock(return_value=None)

        count = service.ingest_feed("https://example.com/feed")

        assert count == 0
        mock_db.add.assert_not_called()

    @patch("src.ingestion.youtube.get_db")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "_parse_feed")
    def test_deduplicates_by_source_id(self, mock_parse_feed, mock_get_db):
        """Existing video (source_id match) is skipped."""
        mock_parse_feed.return_value = [
            {
                "video_id": "existing_vid",
                "title": "Already Ingested",
                "channel_title": "Channel",
                "published_date": datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
                "link": "https://www.youtube.com/watch?v=existing_vid",
            },
        ]

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        # Simulate existing record found
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

        service = YouTubeRSSIngestionService()

        count = service.ingest_feed("https://example.com/feed")

        assert count == 0
        mock_db.add.assert_not_called()

    @patch("src.ingestion.youtube.get_db")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "_parse_feed")
    def test_includes_source_metadata(self, mock_parse_feed, mock_get_db):
        """Content metadata includes source_name, source_tags, and discovery_method."""
        mock_parse_feed.return_value = [
            {
                "video_id": "meta_vid",
                "title": "Metadata Video",
                "channel_title": "Channel",
                "published_date": datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
                "link": "https://www.youtube.com/watch?v=meta_vid",
            },
        ]

        mock_transcript = YouTubeTranscript(
            video_id="meta_vid",
            title="Metadata Video",
            channel_title="Channel",
            segments=[TranscriptSegment(text="Content here", start=0.0, duration=3.0)],
        )

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = YouTubeRSSIngestionService()
        service.client.get_transcript = MagicMock(return_value=mock_transcript)

        count = service.ingest_feed(
            "https://example.com/feed",
            source_name="AI Weekly",
            source_tags=["ai", "weekly"],
        )

        assert count == 1
        added_content = mock_db.add.call_args[0][0]
        metadata = added_content.metadata_json
        assert metadata["source_name"] == "AI Weekly"
        assert metadata["source_tags"] == ["ai", "weekly"]
        assert metadata["discovery_method"] == "rss"


# ---------------------------------------------------------------------------
# TestYouTubeRSSSourceResolution
# ---------------------------------------------------------------------------


class TestYouTubeRSSSourceResolution:
    """Tests for YouTubeRSSIngestionService.ingest_all_feeds()."""

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "ingest_feed", return_value=3)
    def test_uses_sources_parameter(self, mock_ingest_feed):
        """When sources parameter is provided, use them directly."""
        sources = [
            YouTubeRSSSource(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UC1",
                name="Source 1",
            ),
            YouTubeRSSSource(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UC2",
                name="Source 2",
            ),
        ]

        service = YouTubeRSSIngestionService()
        total = service.ingest_all_feeds(sources=sources)

        assert mock_ingest_feed.call_count == 2
        assert total == 6

    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "ingest_feed", return_value=2)
    def test_loads_from_sources_config(self, mock_ingest_feed, mock_settings):
        """When no sources param, loads from SourcesConfig."""
        mock_config = MagicMock()
        mock_config.get_youtube_rss_sources.return_value = [
            YouTubeRSSSource(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UC_config",
                name="Config Source",
            ),
        ]
        mock_settings.get_sources_config.return_value = mock_config

        service = YouTubeRSSIngestionService()
        total = service.ingest_all_feeds()

        mock_settings.get_sources_config.assert_called_once()
        mock_ingest_feed.assert_called_once()
        assert total == 2

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeRSSIngestionService, "ingest_feed", return_value=1)
    def test_per_source_max_entries(self, mock_ingest_feed):
        """source.max_entries overrides max_entries_per_feed."""
        sources = [
            YouTubeRSSSource(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UC_limited",
                name="Limited",
                max_entries=3,
            ),
            YouTubeRSSSource(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UC_default",
                name="Default",
            ),
        ]

        service = YouTubeRSSIngestionService()
        service.ingest_all_feeds(sources=sources, max_entries_per_feed=20)

        assert mock_ingest_feed.call_count == 2
        calls = mock_ingest_feed.call_args_list

        # Build mapping of feed_url to call kwargs for reliable assertion
        call_by_url = {
            call.kwargs.get("feed_url", call.args[0] if call.args else None): call for call in calls
        }

        limited_url = "https://www.youtube.com/feeds/videos.xml?channel_id=UC_limited"
        default_url = "https://www.youtube.com/feeds/videos.xml?channel_id=UC_default"

        assert call_by_url[limited_url].kwargs["max_entries"] == 3
        assert call_by_url[default_url].kwargs["max_entries"] == 20
