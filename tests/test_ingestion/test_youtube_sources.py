"""Tests for config-driven YouTube ingestion.

Tests that YouTubeClient gracefully handles OAuth failures, that
YouTubeContentIngestionService respects visibility flags, uses the
4-tier source resolution chain, and honors per-source settings.
"""

from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

from src.config.sources import YouTubePlaylistSource
from src.ingestion.youtube import YouTubeClient, YouTubeContentIngestionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_init(self, use_oauth=True):
    """Mock YouTubeClient init that avoids real auth."""
    self.service = MagicMock()
    self.use_oauth = use_oauth
    self.oauth_available = False  # Default to no OAuth


# ---------------------------------------------------------------------------
# TestYouTubeOAuthFallback
# ---------------------------------------------------------------------------


class TestYouTubeOAuthFallback:
    """Tests for OAuth graceful degradation in YouTubeClient."""

    @patch.object(YouTubeClient, "_authenticate_api_key")
    @patch.object(YouTubeClient, "_authenticate_oauth")
    def test_oauth_success_sets_flag(self, mock_oauth, mock_api_key):
        """When OAuth succeeds, oauth_available should be True."""
        client = YouTubeClient(use_oauth=True)

        mock_oauth.assert_called_once()
        mock_api_key.assert_not_called()
        assert client.oauth_available is True

    @patch.object(YouTubeClient, "_authenticate_api_key")
    @patch.object(YouTubeClient, "_authenticate_oauth", side_effect=RefreshError("token expired"))
    def test_refresh_error_falls_back_to_api_key(self, mock_oauth, mock_api_key):
        """When _authenticate_oauth raises RefreshError, fall back to API key."""
        client = YouTubeClient(use_oauth=True)

        mock_oauth.assert_called_once()
        mock_api_key.assert_called_once()
        assert client.oauth_available is False

    @patch.object(YouTubeClient, "_authenticate_api_key")
    @patch.object(
        YouTubeClient,
        "_authenticate_oauth",
        side_effect=FileNotFoundError("credentials.json not found"),
    )
    def test_file_not_found_falls_back_to_api_key(self, mock_oauth, mock_api_key):
        """When _authenticate_oauth raises FileNotFoundError, fall back to API key."""
        client = YouTubeClient(use_oauth=True)

        mock_oauth.assert_called_once()
        mock_api_key.assert_called_once()
        assert client.oauth_available is False

    @patch.object(YouTubeClient, "_authenticate_api_key")
    @patch.object(YouTubeClient, "_authenticate_oauth")
    def test_api_key_only_mode(self, mock_oauth, mock_api_key):
        """When use_oauth=False, skip OAuth entirely and oauth_available=False."""
        client = YouTubeClient(use_oauth=False)

        mock_oauth.assert_not_called()
        mock_api_key.assert_called_once()
        assert client.oauth_available is False


# ---------------------------------------------------------------------------
# TestYouTubeVisibilityFiltering
# ---------------------------------------------------------------------------


class TestYouTubeVisibilityFiltering:
    """Tests that private playlists are skipped when OAuth is unavailable."""

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=3)
    def test_private_skipped_without_oauth(self, mock_ingest):
        """Private sources are skipped when client.oauth_available is False."""
        sources = [
            YouTubePlaylistSource(id="PL_private", name="Private", visibility="private"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        total = service.ingest_all_playlists(sources=sources)

        mock_ingest.assert_not_called()
        assert total == 0

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=3)
    def test_private_ingested_with_oauth(self, mock_ingest):
        """Private sources are ingested when client.oauth_available is True."""
        sources = [
            YouTubePlaylistSource(id="PL_private", name="Private", visibility="private"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        total = service.ingest_all_playlists(sources=sources)

        mock_ingest.assert_called_once()
        assert total == 3

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=2)
    def test_public_always_ingested(self, mock_ingest):
        """Public playlists are always ingested regardless of OAuth status."""
        sources = [
            YouTubePlaylistSource(id="PL_public", name="Public", visibility="public"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        total = service.ingest_all_playlists(sources=sources)

        mock_ingest.assert_called_once()
        assert total == 2

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_mixed_visibility_filtering(self, mock_ingest):
        """Only public playlists ingested when OAuth is unavailable."""
        sources = [
            YouTubePlaylistSource(id="PL_pub1", name="Public 1", visibility="public"),
            YouTubePlaylistSource(id="PL_priv", name="Private", visibility="private"),
            YouTubePlaylistSource(id="PL_pub2", name="Public 2", visibility="public"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        total = service.ingest_all_playlists(sources=sources)

        assert mock_ingest.call_count == 2
        ingested_ids = [call.kwargs["playlist_id"] for call in mock_ingest.call_args_list]
        assert "PL_pub1" in ingested_ids
        assert "PL_pub2" in ingested_ids
        assert "PL_priv" not in ingested_ids
        assert total == 2


# ---------------------------------------------------------------------------
# TestYouTubeSourceResolution
# ---------------------------------------------------------------------------


class TestYouTubeSourceResolution:
    """Tests for the 4-tier source resolution in ingest_all_playlists()."""

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_uses_sources_parameter(self, mock_ingest):
        """When sources parameter is provided, use them directly."""
        sources = [
            YouTubePlaylistSource(id="PL_direct", name="Direct Source"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        total = service.ingest_all_playlists(sources=sources)

        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_direct"
        assert total == 1

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_uses_playlist_ids_backward_compat(self, mock_ingest):
        """When playlist_ids provided, wrap them as YouTubePlaylistSource objects."""
        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        total = service.ingest_all_playlists(playlist_ids=["PL_legacy1", "PL_legacy2"])

        assert mock_ingest.call_count == 2
        ingested_ids = [call.kwargs["playlist_id"] for call in mock_ingest.call_args_list]
        assert "PL_legacy1" in ingested_ids
        assert "PL_legacy2" in ingested_ids
        assert total == 2

    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_loads_from_sources_config(self, mock_ingest, mock_settings):
        """When no parameters, load from settings.get_sources_config()."""
        mock_config = MagicMock()
        mock_config.get_youtube_playlist_sources.return_value = [
            YouTubePlaylistSource(id="PL_config", name="Config Source"),
        ]
        mock_settings.get_sources_config.return_value = mock_config

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        total = service.ingest_all_playlists()

        mock_settings.get_sources_config.assert_called_once()
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_config"
        assert total == 1

    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_falls_back_to_legacy(self, mock_ingest, mock_settings):
        """When SourcesConfig has no playlists, fall back to legacy settings."""
        mock_config = MagicMock()
        mock_config.get_youtube_playlist_sources.return_value = []
        mock_settings.get_sources_config.return_value = mock_config
        mock_settings.get_youtube_playlists.return_value = [
            {"id": "PL_legacy", "description": "Legacy Playlist"},
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        total = service.ingest_all_playlists()

        mock_settings.get_youtube_playlists.assert_called_once()
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_legacy"
        assert total == 1


# ---------------------------------------------------------------------------
# TestYouTubePerSourceSettings
# ---------------------------------------------------------------------------


class TestYouTubePerSourceSettings:
    """Tests for per-source max_entries and enabled flag."""

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_per_source_max_entries_override(self, mock_ingest):
        """source.max_entries overrides the default max_videos_per_playlist."""
        sources = [
            YouTubePlaylistSource(id="PL_limited", name="Limited", max_entries=5),
            YouTubePlaylistSource(id="PL_default", name="Default"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        service.ingest_all_playlists(sources=sources, max_videos_per_playlist=20)

        assert mock_ingest.call_count == 2
        calls = mock_ingest.call_args_list

        # Find which call corresponds to which source
        call_by_id = {call.kwargs["playlist_id"]: call for call in calls}
        assert call_by_id["PL_limited"].kwargs["max_videos"] == 5
        assert call_by_id["PL_default"].kwargs["max_videos"] == 20

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", return_value=1)
    def test_disabled_sources_skipped(self, mock_ingest):
        """Sources with enabled=False are filtered out."""
        sources = [
            YouTubePlaylistSource(id="PL_active", name="Active"),
            YouTubePlaylistSource(id="PL_disabled", name="Disabled", enabled=False),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        total = service.ingest_all_playlists(sources=sources)

        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_active"
        assert total == 1
