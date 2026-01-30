"""Tests for config-driven RSS ingestion.

Tests that RSSContentIngestionService correctly uses RSSSource objects
from the unified source configuration, respecting enabled flags,
per-source max_entries, and including source metadata in content records.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.config.sources import RSSSource
from src.ingestion.rss import RSSClient, RSSContentIngestionService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_feed_response():
    """Create a mock feedparser response with entries."""

    def _make_feed(entries=None):
        feed = MagicMock()
        feed.bozo = False
        feed.feed = MagicMock()
        feed.feed.title = "Test Feed"
        feed.entries = entries or []
        return feed

    return _make_feed


@pytest.fixture
def mock_entry():
    """Create a mock feed entry."""

    def _make_entry(title="Test Article", link="https://example.com/article"):
        entry = MagicMock()
        entry.get = lambda key, default=None: {
            "title": title,
            "link": link,
            "id": f"entry-{title}",
            "author": "Test Author",
        }.get(key, default)
        entry.title = title
        entry.link = link
        entry.id = f"entry-{title}"
        entry.author = "Test Author"
        entry.published_parsed = (2025, 1, 15, 10, 0, 0, 0, 0, 0)
        entry.content = [{"type": "text/html", "value": f"<p>{title} content</p>"}]
        return entry

    return _make_entry


# ---------------------------------------------------------------------------
# RSSClient source metadata tests
# ---------------------------------------------------------------------------


class TestRSSClientSourceMetadata:
    """Tests that RSSClient passes source metadata through to ContentData."""

    def test_fetch_content_includes_source_name(self, mock_feed_response, mock_entry):
        """Source name from config should appear in content metadata."""
        feed = mock_feed_response([mock_entry()])

        with (
            patch("src.ingestion.rss.httpx.Client") as mock_http,
            patch("src.ingestion.rss.feedparser.parse", return_value=feed),
            patch("src.ingestion.rss.convert_html_to_markdown", return_value="# Test"),
        ):
            mock_response = MagicMock()
            mock_response.content = b"<rss></rss>"
            mock_http.return_value.get.return_value = mock_response

            client = RSSClient()
            contents = client.fetch_content(
                feed_url="https://example.com/feed",
                source_name="My RSS Feed",
                source_tags=["ai", "news"],
            )

        assert len(contents) == 1
        assert contents[0].metadata_json["source_name"] == "My RSS Feed"
        assert contents[0].metadata_json["source_tags"] == ["ai", "news"]

    def test_fetch_content_without_source_metadata(self, mock_feed_response, mock_entry):
        """Without source metadata, metadata_json should not include those keys."""
        feed = mock_feed_response([mock_entry()])

        with (
            patch("src.ingestion.rss.httpx.Client") as mock_http,
            patch("src.ingestion.rss.feedparser.parse", return_value=feed),
            patch("src.ingestion.rss.convert_html_to_markdown", return_value="# Test"),
        ):
            mock_response = MagicMock()
            mock_response.content = b"<rss></rss>"
            mock_http.return_value.get.return_value = mock_response

            client = RSSClient()
            contents = client.fetch_content(
                feed_url="https://example.com/feed",
            )

        assert len(contents) == 1
        assert "source_name" not in contents[0].metadata_json
        assert "source_tags" not in contents[0].metadata_json
        assert "feed_url" in contents[0].metadata_json


# ---------------------------------------------------------------------------
# RSSContentIngestionService source resolution tests
# ---------------------------------------------------------------------------


class TestRSSSourceResolution:
    """Tests for the source resolution fallback chain in ingest_content()."""

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_uses_sources_parameter_directly(self, mock_settings, mock_db):
        """When sources parameter is provided, use it directly."""
        sources = [
            RSSSource(url="https://a.com/feed", name="Feed A"),
            RSSSource(url="https://b.com/feed", name="Feed B"),
        ]

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content(sources=sources)

        assert mock_fetch.call_count == 2
        calls = mock_fetch.call_args_list
        assert calls[0].kwargs["feed_url"] == "https://a.com/feed"
        assert calls[0].kwargs["source_name"] == "Feed A"
        assert calls[1].kwargs["feed_url"] == "https://b.com/feed"
        assert calls[1].kwargs["source_name"] == "Feed B"

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_uses_feed_urls_parameter_backward_compat(self, mock_settings, mock_db):
        """When feed_urls parameter is provided, convert to RSSSource objects."""
        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content(feed_urls=["https://a.com/feed", "https://b.com/feed"])

        assert mock_fetch.call_count == 2
        calls = mock_fetch.call_args_list
        assert calls[0].kwargs["feed_url"] == "https://a.com/feed"
        assert calls[1].kwargs["feed_url"] == "https://b.com/feed"

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_loads_from_sources_config(self, mock_settings, mock_db):
        """When no parameters, load from SourcesConfig."""
        mock_config = MagicMock()
        mock_config.get_rss_sources.return_value = [
            RSSSource(url="https://config.com/feed", name="Config Feed"),
        ]
        mock_settings.get_sources_config.return_value = mock_config

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content()

        mock_settings.get_sources_config.assert_called_once()
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args.kwargs["feed_url"] == "https://config.com/feed"
        assert mock_fetch.call_args.kwargs["source_name"] == "Config Feed"

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_falls_back_to_legacy_urls(self, mock_settings, mock_db):
        """When SourcesConfig is empty, fall back to legacy get_rss_feed_urls()."""
        mock_config = MagicMock()
        mock_config.get_rss_sources.return_value = []
        mock_settings.get_sources_config.return_value = mock_config
        mock_settings.get_rss_feed_urls.return_value = ["https://legacy.com/feed"]

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content()

        mock_settings.get_rss_feed_urls.assert_called_once()
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args.kwargs["feed_url"] == "https://legacy.com/feed"

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_returns_zero_when_no_sources(self, mock_settings, mock_db):
        """When no sources found anywhere, return 0 without error."""
        mock_config = MagicMock()
        mock_config.get_rss_sources.return_value = []
        mock_settings.get_sources_config.return_value = mock_config
        mock_settings.get_rss_feed_urls.return_value = []

        service = RSSContentIngestionService()
        count = service.ingest_content()

        assert count == 0


# ---------------------------------------------------------------------------
# Per-source settings tests
# ---------------------------------------------------------------------------


class TestRSSPerSourceSettings:
    """Tests for per-source max_entries and enabled flag."""

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_disabled_sources_are_skipped(self, mock_settings, mock_db):
        """Sources with enabled=False should not be fetched."""
        sources = [
            RSSSource(url="https://a.com/feed", name="Active"),
            RSSSource(url="https://b.com/feed", name="Disabled", enabled=False),
        ]

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content(sources=sources)

        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args.kwargs["feed_url"] == "https://a.com/feed"

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_per_source_max_entries_override(self, mock_settings, mock_db):
        """Source.max_entries overrides the default max_entries_per_feed."""
        sources = [
            RSSSource(url="https://a.com/feed", max_entries=5),
            RSSSource(url="https://b.com/feed"),  # Should use default
        ]

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content(sources=sources, max_entries_per_feed=20)

        calls = mock_fetch.call_args_list
        assert calls[0].kwargs["max_entries"] == 5  # Per-source override
        assert calls[1].kwargs["max_entries"] == 20  # Default

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_source_tags_passed_to_client(self, mock_settings, mock_db):
        """Source tags should be passed through to the client."""
        sources = [
            RSSSource(url="https://a.com/feed", name="Tagged", tags=["ai", "ml"]),
        ]

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content(sources=sources)

        assert mock_fetch.call_args.kwargs["source_tags"] == ["ai", "ml"]

    @patch("src.ingestion.rss.get_db")
    @patch("src.ingestion.rss.settings")
    def test_empty_tags_passed_as_none(self, mock_settings, mock_db):
        """Empty tags list should be passed as None (not empty list)."""
        sources = [
            RSSSource(url="https://a.com/feed"),
        ]

        with patch.object(RSSClient, "fetch_content", return_value=[]) as mock_fetch:
            service = RSSContentIngestionService()
            service.ingest_content(sources=sources)

        assert mock_fetch.call_args.kwargs["source_tags"] is None
