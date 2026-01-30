"""Tests for podcast ingestion with transcript-first strategy."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.config.sources import PodcastSource
from src.ingestion.podcast import (
    MIN_TRANSCRIPT_LENGTH,
    PodcastClient,
    PodcastContentIngestionService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_episode():
    """A complete episode dict as returned by PodcastClient.fetch_feed()."""
    return {
        "guid": "episode-abc-123",
        "title": "Deep Dive into LLM Architectures",
        "link": "https://example.com/episodes/llm-architectures",
        "published_date": datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
        "description": "Short episode description.",
        "content_encoded": "",
        "itunes_summary": "",
        "audio_url": "https://cdn.example.com/episodes/llm-arch.mp3",
        "duration": "45:32",
        "author": "Jane Smith",
        "feed_title": "AI Weekly Podcast",
    }


@pytest.fixture
def long_text():
    """Return a string guaranteed to exceed MIN_TRANSCRIPT_LENGTH."""
    return "A" * (MIN_TRANSCRIPT_LENGTH + 100)


@pytest.fixture
def short_text():
    """Return a string below MIN_TRANSCRIPT_LENGTH."""
    return "A" * (MIN_TRANSCRIPT_LENGTH - 100)


# ---------------------------------------------------------------------------
# Helper: mock feedparser entry with enclosure
# ---------------------------------------------------------------------------


def _make_feedparser_entry(
    *,
    guid="ep-1",
    title="Episode Title",
    link="https://example.com/ep/1",
    published_parsed=(2025, 1, 20, 10, 0, 0, 0, 0, 0),
    description="Short description",
    content_encoded="",
    itunes_summary="",
    enclosure_href="https://cdn.example.com/ep1.mp3",
    enclosure_type="audio/mpeg",
    author="Host Name",
    feed_title="My Podcast",
):
    """Build a dict-backed mock that behaves like a feedparser entry.

    feedparser entries support both attribute access AND .get() for dict keys.
    The implementation uses .get() for most fields, so we back with a real dict.
    """
    # Build enclosures as dicts (feedparser enclosures support .get())
    enclosures = []
    if enclosure_href:
        enclosures = [{"type": enclosure_type, "href": enclosure_href}]

    # Content list (feedparser stores content:encoded as list of dicts)
    content_list = []
    if content_encoded:
        content_list = [{"type": "text/html", "value": content_encoded}]

    # Backing data for .get() calls
    data = {
        "id": guid,
        "title": title,
        "link": link,
        "author": author,
        "summary": description,
        "content": content_list,
        "itunes_summary": itunes_summary,
        "enclosures": enclosures,
        "itunes_duration": "",
    }

    entry = MagicMock()
    entry.get = lambda key, default=None: data.get(key, default)
    entry.published_parsed = published_parsed
    # Support hasattr checks and attribute access
    entry.id = guid
    entry.title = title
    entry.link = link

    return entry, feed_title


# ---------------------------------------------------------------------------
# TestPodcastClientFeedParsing
# ---------------------------------------------------------------------------


class TestPodcastClientFeedParsing:
    """Tests for PodcastClient.fetch_feed() feed parsing."""

    @patch("src.ingestion.podcast.feedparser")
    def test_parses_podcast_feed(self, mock_feedparser):
        """Mock feedparser returns entries with enclosures; verify extracted metadata."""
        entry, feed_title = _make_feedparser_entry(
            guid="ep-42",
            title="Understanding Transformers",
            link="https://example.com/ep/42",
            author="Alice",
            enclosure_href="https://cdn.example.com/ep42.mp3",
        )
        mock_feed = MagicMock()
        mock_feed.feed.get = lambda key, default="": {"title": feed_title}.get(key, default)
        mock_feed.entries = [entry]
        mock_feed.bozo = False
        mock_feedparser.parse.return_value = mock_feed

        client = PodcastClient()
        episodes = client.fetch_feed("https://example.com/feed.xml", max_entries=10)

        assert len(episodes) == 1
        ep = episodes[0]
        assert ep["guid"] == "ep-42"
        assert ep["title"] == "Understanding Transformers"
        assert ep["link"] == "https://example.com/ep/42"
        assert ep["author"] == "Alice"
        assert ep["feed_title"] == feed_title

    @patch("src.ingestion.podcast.feedparser")
    def test_extracts_audio_url_from_enclosure(self, mock_feedparser):
        """Entry with audio/mpeg enclosure extracts the href as audio_url."""
        entry, feed_title = _make_feedparser_entry(
            enclosure_href="https://cdn.example.com/audio.mp3",
            enclosure_type="audio/mpeg",
        )
        mock_feed = MagicMock()
        mock_feed.feed.get = lambda key, default="": {"title": feed_title}.get(key, default)
        mock_feed.entries = [entry]
        mock_feed.bozo = False
        mock_feedparser.parse.return_value = mock_feed

        client = PodcastClient()
        episodes = client.fetch_feed("https://example.com/feed.xml")

        assert len(episodes) == 1
        assert episodes[0]["audio_url"] == "https://cdn.example.com/audio.mp3"

    @patch("src.ingestion.podcast.feedparser")
    def test_handles_empty_feed(self, mock_feedparser):
        """Feed with no entries returns empty list."""
        mock_feed = MagicMock()
        mock_feed.feed.get = lambda key, default="": {"title": "Empty Podcast"}.get(key, default)
        mock_feed.entries = []
        mock_feed.bozo = False
        mock_feedparser.parse.return_value = mock_feed

        client = PodcastClient()
        episodes = client.fetch_feed("https://example.com/empty-feed.xml")

        assert episodes == []


# ---------------------------------------------------------------------------
# TestPodcastTranscriptTiers
# ---------------------------------------------------------------------------


class TestPodcastTranscriptTiers:
    """Tests for the tiered transcript extraction strategy."""

    def test_tier1_content_encoded_long_enough(self, sample_episode, long_text):
        """content_encoded with >= MIN_TRANSCRIPT_LENGTH chars returns that text."""
        sample_episode["content_encoded"] = long_text

        client = PodcastClient()
        result = client.extract_transcript_from_feed(sample_episode)

        assert result is not None
        assert len(result) >= MIN_TRANSCRIPT_LENGTH

    def test_tier1_short_text_returns_none(self, sample_episode, short_text):
        """content_encoded with < MIN_TRANSCRIPT_LENGTH chars returns None."""
        sample_episode["content_encoded"] = short_text
        sample_episode["description"] = "Also short."
        sample_episode["itunes_summary"] = ""

        client = PodcastClient()
        result = client.extract_transcript_from_feed(sample_episode)

        assert result is None

    def test_tier1_falls_through_to_description(self, sample_episode, long_text):
        """Empty content_encoded but long description returns description."""
        sample_episode["content_encoded"] = ""
        sample_episode["description"] = long_text

        client = PodcastClient()
        result = client.extract_transcript_from_feed(sample_episode)

        assert result is not None
        assert result == long_text

    @patch("src.parsers.html_markdown.convert_html_to_markdown")
    @patch("src.ingestion.podcast.httpx")
    def test_tier2_detects_transcript_url(self, mock_httpx, mock_convert, sample_episode):
        """Episode with /transcript URL in description triggers HTTP fetch."""
        transcript_url = "https://example.com/episodes/llm-architectures/transcript"
        sample_episode["description"] = f"Show notes and full transcript: {transcript_url}"
        sample_episode["content_encoded"] = ""
        sample_episode["itunes_summary"] = ""

        long_transcript = "Full transcript text content " * 50
        mock_response = MagicMock()
        mock_response.text = "<html>" + long_transcript + "</html>"
        mock_response.raise_for_status = MagicMock()

        # httpx.Client() used as context manager
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_httpx.Client.return_value.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)

        mock_convert.return_value = long_transcript

        client = PodcastClient()
        result = client.extract_transcript_from_url(sample_episode)

        assert result is not None
        assert result == long_transcript
        mock_client_instance.get.assert_called_once()

    def test_tier2_no_transcript_url_returns_none(self, sample_episode):
        """Episode without transcript URLs in text returns None."""
        sample_episode["description"] = (
            "Just a regular show notes link: https://example.com/episode"
        )
        sample_episode["content_encoded"] = ""
        sample_episode["itunes_summary"] = ""

        client = PodcastClient()
        result = client.extract_transcript_from_url(sample_episode)

        assert result is None


# ---------------------------------------------------------------------------
# TestPodcastIngestion — PodcastContentIngestionService
# ---------------------------------------------------------------------------


def _mock_service_init(self):
    """Mock PodcastContentIngestionService.__init__ to avoid real setup."""
    self.client = MagicMock()


class TestPodcastIngestion:
    """Tests for PodcastContentIngestionService.ingest_feed()."""

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch("src.ingestion.podcast.get_db")
    def test_ingests_episode_with_tier1_transcript(self, mock_get_db):
        """Feed-embedded transcript creates Content with raw_format='feed_transcript'."""
        long_transcript = "Detailed episode transcript. " * 50

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        # No existing record
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = PodcastContentIngestionService()
        # Client returns one episode
        service.client.fetch_feed.return_value = [
            {
                "guid": "ep-tier1",
                "title": "Tier 1 Episode",
                "link": "https://example.com/ep/tier1",
                "published_date": datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
                "description": "Short desc",
                "content_encoded": long_transcript,
                "itunes_summary": "",
                "audio_url": "https://cdn.example.com/tier1.mp3",
                "duration": "30:00",
                "author": "Host",
                "feed_title": "Test Podcast",
            }
        ]
        # Tier 1 returns transcript from feed
        service.client.extract_transcript_from_feed.return_value = long_transcript

        count = service.ingest_feed("https://example.com/feed.xml")

        assert count >= 1
        mock_db.add.assert_called()
        added_content = mock_db.add.call_args[0][0]
        assert added_content.raw_format == "feed_transcript"

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch("src.ingestion.podcast.get_db")
    def test_tier2_fallback_when_tier1_fails(self, mock_get_db):
        """Short feed text but linked transcript found -> raw_format='linked_transcript'."""
        linked_transcript = "Full linked transcript content. " * 50

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = PodcastContentIngestionService()
        service.client.fetch_feed.return_value = [
            {
                "guid": "ep-tier2",
                "title": "Tier 2 Episode",
                "link": "https://example.com/ep/tier2",
                "published_date": datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
                "description": "See transcript at https://example.com/transcript",
                "content_encoded": "Too short",
                "itunes_summary": "",
                "audio_url": "https://cdn.example.com/tier2.mp3",
                "duration": "40:00",
                "author": "Host",
                "feed_title": "Test Podcast",
            }
        ]
        # Tier 1 fails (text too short)
        service.client.extract_transcript_from_feed.return_value = None
        # Tier 2 succeeds
        service.client.extract_transcript_from_url.return_value = linked_transcript

        count = service.ingest_feed("https://example.com/feed.xml")

        assert count >= 1
        mock_db.add.assert_called()
        added_content = mock_db.add.call_args[0][0]
        assert added_content.raw_format == "linked_transcript"

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch("src.ingestion.podcast.get_db")
    def test_skips_episode_without_transcript(self, mock_get_db):
        """No transcript from any tier -> episode skipped (count=0)."""
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db

        service = PodcastContentIngestionService()
        service.client.fetch_feed.return_value = [
            {
                "guid": "ep-none",
                "title": "No Transcript Episode",
                "link": "https://example.com/ep/none",
                "published_date": datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
                "description": "No transcript available.",
                "content_encoded": "",
                "itunes_summary": "",
                "audio_url": "https://cdn.example.com/none.mp3",
                "duration": "25:00",
                "author": "Host",
                "feed_title": "Test Podcast",
            }
        ]
        # All tiers fail
        service.client.extract_transcript_from_feed.return_value = None
        service.client.extract_transcript_from_url.return_value = None

        count = service.ingest_feed("https://example.com/feed.xml", transcribe=False)

        assert count == 0
        mock_db.add.assert_not_called()

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch("src.ingestion.podcast.get_db")
    def test_deduplicates_by_source_id(self, mock_get_db):
        """Existing podcast:{guid} in DB -> episode skipped."""
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        # Return an existing record (dedup hit)
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

        service = PodcastContentIngestionService()
        service.client.fetch_feed.return_value = [
            {
                "guid": "ep-existing",
                "title": "Existing Episode",
                "link": "https://example.com/ep/existing",
                "published_date": datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
                "description": "Already ingested.",
                "content_encoded": "Full transcript content. " * 50,
                "itunes_summary": "",
                "audio_url": "https://cdn.example.com/existing.mp3",
                "duration": "35:00",
                "author": "Host",
                "feed_title": "Test Podcast",
            }
        ]
        service.client.extract_transcript_from_feed.return_value = "Full transcript content. " * 50

        count = service.ingest_feed("https://example.com/feed.xml")

        assert count == 0
        mock_db.add.assert_not_called()

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch("src.ingestion.podcast.get_db")
    def test_source_metadata_in_content(self, mock_get_db):
        """source_name, source_tags stored in metadata_json."""
        long_transcript = "Episode transcript text content. " * 50

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = PodcastContentIngestionService()
        service.client.fetch_feed.return_value = [
            {
                "guid": "ep-meta",
                "title": "Metadata Episode",
                "link": "https://example.com/ep/meta",
                "published_date": datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
                "description": "Short desc",
                "content_encoded": long_transcript,
                "itunes_summary": "",
                "audio_url": "https://cdn.example.com/meta.mp3",
                "duration": "50:00",
                "author": "Host",
                "feed_title": "AI Weekly",
            }
        ]
        service.client.extract_transcript_from_feed.return_value = long_transcript

        count = service.ingest_feed(
            "https://example.com/feed.xml",
            source_name="AI Weekly Podcast",
            source_tags=["ai", "ml", "podcast"],
        )

        assert count >= 1
        mock_db.add.assert_called()
        added_content = mock_db.add.call_args[0][0]
        assert added_content.metadata_json["source_name"] == "AI Weekly Podcast"
        assert added_content.metadata_json["source_tags"] == [
            "ai",
            "ml",
            "podcast",
        ]


# ---------------------------------------------------------------------------
# TestPodcastSourceResolution
# ---------------------------------------------------------------------------


class TestPodcastSourceResolution:
    """Tests for source resolution in ingest_all_feeds()."""

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch.object(PodcastContentIngestionService, "ingest_feed", return_value=3)
    def test_uses_sources_parameter(self, mock_ingest_feed):
        """Explicit PodcastSource list used directly."""
        sources = [
            PodcastSource(url="https://a.com/feed.xml", name="Podcast A"),
            PodcastSource(url="https://b.com/feed.xml", name="Podcast B"),
        ]

        service = PodcastContentIngestionService()
        total = service.ingest_all_feeds(sources=sources)

        assert mock_ingest_feed.call_count == 2
        calls = mock_ingest_feed.call_args_list
        assert calls[0].kwargs.get("feed_url") or calls[0].args[0] is not None
        assert total == 6  # 3 per feed * 2 feeds

    @patch("src.ingestion.podcast.settings")
    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch.object(PodcastContentIngestionService, "ingest_feed", return_value=2)
    def test_loads_from_sources_config(self, mock_ingest_feed, mock_settings):
        """Falls through to settings.get_sources_config().get_podcast_sources()."""
        mock_config = MagicMock()
        mock_config.get_podcast_sources.return_value = [
            PodcastSource(url="https://config.com/feed.xml", name="Config Podcast"),
        ]
        mock_settings.get_sources_config.return_value = mock_config

        service = PodcastContentIngestionService()
        total = service.ingest_all_feeds()

        mock_settings.get_sources_config.assert_called_once()
        assert mock_ingest_feed.call_count == 1
        assert total == 2

    @patch.object(PodcastContentIngestionService, "__init__", _mock_service_init)
    @patch.object(PodcastContentIngestionService, "ingest_feed", return_value=5)
    def test_per_source_settings_passed(self, mock_ingest_feed):
        """source.transcribe, stt_provider, languages passed through to ingest_feed()."""
        sources = [
            PodcastSource(
                url="https://german.com/feed.xml",
                name="German Podcast",
                transcribe=True,
                stt_provider="local_whisper",
                languages=["de", "en"],
            ),
        ]

        service = PodcastContentIngestionService()
        service.ingest_all_feeds(sources=sources)

        assert mock_ingest_feed.call_count == 1
        call_kwargs = mock_ingest_feed.call_args.kwargs
        # Verify per-source settings are forwarded
        assert call_kwargs.get("transcribe") is True
        assert call_kwargs.get("stt_provider") == "local_whisper"
        assert call_kwargs.get("languages") == ["de", "en"]


# ---------------------------------------------------------------------------
# TestPodcastMarkdownConversion
# ---------------------------------------------------------------------------


class TestPodcastMarkdownConversion:
    """Tests for _to_markdown() episode-to-markdown conversion."""

    def test_markdown_includes_metadata(self, sample_episode):
        """Output includes title, podcast name, host, published date, duration."""
        transcript = "This is the full transcript of the episode."

        service = PodcastContentIngestionService.__new__(PodcastContentIngestionService)
        result = service._to_markdown(sample_episode, transcript)

        assert sample_episode["title"] in result
        assert sample_episode["feed_title"] in result
        assert sample_episode["author"] in result
        assert sample_episode["duration"] in result

    def test_markdown_includes_transcript(self, sample_episode):
        """Output includes '## Transcript' section with transcript text."""
        transcript = "Welcome to the show. Today we discuss large language models."

        service = PodcastContentIngestionService.__new__(PodcastContentIngestionService)
        result = service._to_markdown(sample_episode, transcript)

        assert "## Transcript" in result
        assert transcript in result
