"""Tests for config-driven YouTube ingestion.

Tests that YouTubeClient gracefully handles OAuth failures, that
YouTubeContentIngestionService respects visibility flags, uses the
4-tier source resolution chain, and honors per-source settings.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from src.config.sources import (
    SourcesConfig,
    YouTubeChannelSource,
    YouTubePlaylistSource,
    use_sources_config,
)
from src.ingestion.youtube import (
    SourceFetchResult,
    YouTubeClient,
    YouTubeContentIngestionService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_init(self, use_oauth=True):
    """Mock YouTubeClient init that avoids real auth."""
    self._service = MagicMock()
    self._authenticated = True
    self.use_oauth = use_oauth
    self.oauth_available = False  # Default to no OAuth


def _yt_fetch_builder(items_fetched: int):
    """Builder for ingest_playlist AsyncMock side_effect.

    Returns a fresh ``SourceFetchResult`` per call so aggregator-side mutation
    of ``result.name`` (and for channels, ``result.url``) doesn't leak across
    calls. ``return_value=`` shares one instance — incompatible with how the
    aggregator overrides per-source identity on each result.
    """

    def _build(*args, **kwargs):
        playlist_id = kwargs.get("playlist_id", "PL_mock")
        return SourceFetchResult(
            url=f"https://www.youtube.com/playlist?list={playlist_id}",
            items_fetched=items_fetched,
        )

    return _build


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

        # Auth is lazy — trigger it by accessing .service
        _ = client.service

        mock_oauth.assert_called_once()
        mock_api_key.assert_not_called()
        assert client.oauth_available is True

    @patch.object(YouTubeClient, "_authenticate_api_key")
    @patch.object(YouTubeClient, "_authenticate_oauth", side_effect=RefreshError("token expired"))
    def test_refresh_error_falls_back_to_api_key(self, mock_oauth, mock_api_key):
        """When _authenticate_oauth raises RefreshError, fall back to API key."""
        client = YouTubeClient(use_oauth=True)

        # Auth is lazy — trigger it by accessing .service
        _ = client.service

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

        # Auth is lazy — trigger it by accessing .service
        _ = client.service

        mock_oauth.assert_called_once()
        mock_api_key.assert_called_once()
        assert client.oauth_available is False

    @patch.object(YouTubeClient, "_authenticate_api_key")
    @patch.object(YouTubeClient, "_authenticate_oauth")
    def test_api_key_only_mode(self, mock_oauth, mock_api_key):
        """When use_oauth=False, skip OAuth entirely and oauth_available=False."""
        client = YouTubeClient(use_oauth=False)

        # Auth is lazy — trigger it by accessing .service
        _ = client.service

        mock_oauth.assert_not_called()
        mock_api_key.assert_called_once()
        assert client.oauth_available is False

    def test_no_auth_without_service_access(self):
        """Client creation without accessing .service doesn't trigger auth."""
        client = YouTubeClient(use_oauth=False)

        # No auth triggered yet
        assert client._authenticated is False
        assert client.oauth_available is False


# ---------------------------------------------------------------------------
# TestYouTubeVisibilityFiltering
# ---------------------------------------------------------------------------


class TestYouTubeVisibilityFiltering:
    """Tests that private playlists are skipped when OAuth is unavailable."""

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(3),
    )
    async def test_private_skipped_without_oauth(self, mock_ingest, mock_settings):
        """Private sources are skipped when client.oauth_available is False."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_private", name="Private", visibility="private"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        response = await service.ingest_all_playlists(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_not_called()
        assert total == 0

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(3),
    )
    async def test_private_ingested_with_oauth(self, mock_ingest, mock_settings):
        """Private sources are ingested when client.oauth_available is True."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_private", name="Private", visibility="private"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        response = await service.ingest_all_playlists(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_called_once()
        assert total == 3

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(2),
    )
    async def test_public_always_ingested(self, mock_ingest, mock_settings):
        """Public playlists are always ingested regardless of OAuth status."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_public", name="Public", visibility="public"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        response = await service.ingest_all_playlists(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_called_once()
        assert total == 2

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_mixed_visibility_filtering(self, mock_ingest, mock_settings):
        """Only public playlists ingested when OAuth is unavailable."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_pub1", name="Public 1", visibility="public"),
            YouTubePlaylistSource(id="PL_priv", name="Private", visibility="private"),
            YouTubePlaylistSource(id="PL_pub2", name="Public 2", visibility="public"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        response = await service.ingest_all_playlists(sources=sources)
        total = response.items_ingested

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

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_uses_sources_parameter(self, mock_ingest, mock_settings):
        """When sources parameter is provided, use them directly."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_direct", name="Direct Source"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        response = await service.ingest_all_playlists(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_direct"
        assert total == 1

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_uses_playlist_ids_backward_compat(self, mock_ingest, mock_settings):
        """When playlist_ids provided, wrap them as YouTubePlaylistSource objects."""
        mock_settings.youtube_max_concurrent_playlists = 3
        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        response = await service.ingest_all_playlists(playlist_ids=["PL_legacy1", "PL_legacy2"])
        total = response.items_ingested

        assert mock_ingest.call_count == 2
        ingested_ids = [call.kwargs["playlist_id"] for call in mock_ingest.call_args_list]
        assert "PL_legacy1" in ingested_ids
        assert "PL_legacy2" in ingested_ids
        assert total == 2

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_loads_from_sources_config(self, mock_ingest, mock_settings):
        """When no parameters, load from settings.get_sources_config()."""
        mock_settings.youtube_max_concurrent_playlists = 3
        mock_config = MagicMock()
        mock_config.get_youtube_playlist_sources.return_value = [
            YouTubePlaylistSource(id="PL_config", name="Config Source"),
        ]
        mock_settings.get_sources_config.return_value = mock_config

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        response = await service.ingest_all_playlists()
        total = response.items_ingested

        mock_settings.get_sources_config.assert_called_once()
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_config"
        assert total == 1

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_falls_back_to_legacy(self, mock_ingest, mock_settings):
        """When SourcesConfig has no playlists, fall back to legacy settings."""
        mock_settings.youtube_max_concurrent_playlists = 3
        mock_config = MagicMock()
        mock_config.get_youtube_playlist_sources.return_value = []
        mock_settings.get_sources_config.return_value = mock_config
        mock_settings.get_youtube_playlists.return_value = [
            {"id": "PL_legacy", "description": "Legacy Playlist"},
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        response = await service.ingest_all_playlists()
        total = response.items_ingested

        mock_settings.get_youtube_playlists.assert_called_once()
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_legacy"
        assert total == 1

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(YouTubeContentIngestionService, "ingest_playlist", new_callable=AsyncMock)
    async def test_channel_only_snapshot_does_not_fall_back_to_legacy_playlists(
        self,
        mock_ingest,
        mock_settings,
    ):
        config = SourcesConfig(
            sources=[YouTubeChannelSource(channel_id="UC_queued", name="Queued channel")]
        )
        mock_settings.get_sources_config.return_value = config
        mock_settings.get_youtube_playlists.return_value = [
            {"id": "PL_legacy", "description": "Legacy Playlist"}
        ]
        service = YouTubeContentIngestionService()

        with use_sources_config(config):
            response = await service.ingest_all_playlists()

        assert response.items_ingested == 0
        mock_settings.get_youtube_playlists.assert_not_called()
        mock_ingest.assert_not_called()


# ---------------------------------------------------------------------------
# TestYouTubePerSourceSettings
# ---------------------------------------------------------------------------


class TestYouTubePerSourceSettings:
    """Tests for per-source max_entries and enabled flag."""

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_per_source_max_entries_override(self, mock_ingest, mock_settings):
        """source.max_entries overrides the default max_videos_per_playlist."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_limited", name="Limited", max_entries=5),
            YouTubePlaylistSource(id="PL_default", name="Default"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        await service.ingest_all_playlists(sources=sources, max_videos_per_playlist=20)

        assert mock_ingest.call_count == 2
        calls = mock_ingest.call_args_list

        # Find which call corresponds to which source
        call_by_id = {call.kwargs["playlist_id"]: call for call in calls}
        assert call_by_id["PL_limited"].kwargs["max_videos"] == 5
        assert call_by_id["PL_default"].kwargs["max_videos"] == 20

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_disabled_sources_skipped(self, mock_ingest, mock_settings):
        """Sources with enabled=False are filtered out."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubePlaylistSource(id="PL_active", name="Active"),
            YouTubePlaylistSource(id="PL_disabled", name="Disabled", enabled=False),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True

        response = await service.ingest_all_playlists(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "PL_active"
        assert total == 1


# ---------------------------------------------------------------------------
# TestYouTubeChannelResolution
# ---------------------------------------------------------------------------


class TestYouTubeChannelResolution:
    """Tests for YouTubeClient.resolve_channel_to_playlist()."""

    @patch.object(YouTubeClient, "__init__", _mock_init)
    def test_resolves_channel_to_uploads_playlist(self):
        """Channel ID should resolve to uploads playlist ID."""
        client = YouTubeClient()
        client.service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_uploads_123"}}}]
        }
        # Clear class-level cache for test isolation
        YouTubeClient._channel_playlist_cache = {}

        result = client.resolve_channel_to_playlist("UC_channel_123")

        assert result == "UU_uploads_123"
        client.service.channels.return_value.list.assert_called_once_with(
            part="contentDetails",
            id="UC_channel_123",
        )

    @patch.object(YouTubeClient, "__init__", _mock_init)
    def test_returns_none_for_unknown_channel(self):
        """Unknown channel should return None."""
        client = YouTubeClient()
        client.service.channels.return_value.list.return_value.execute.return_value = {"items": []}
        YouTubeClient._channel_playlist_cache = {}

        result = client.resolve_channel_to_playlist("UC_nonexistent")

        assert result is None

    @patch.object(YouTubeClient, "__init__", _mock_init)
    def test_caches_resolved_playlist(self):
        """Second call for same channel should use cache, not API."""
        client = YouTubeClient()
        client.service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_cached"}}}]
        }
        YouTubeClient._channel_playlist_cache = {}

        # First call hits API
        result1 = client.resolve_channel_to_playlist("UC_cached_test")
        # Second call should use cache
        result2 = client.resolve_channel_to_playlist("UC_cached_test")

        assert result1 == "UU_cached"
        assert result2 == "UU_cached"
        # API should only be called once
        assert client.service.channels.return_value.list.return_value.execute.call_count == 1

    @patch.object(YouTubeClient, "__init__", _mock_init)
    def test_handles_http_error(self):
        """HttpError from API should return None, not raise."""
        client = YouTubeClient()
        resp = MagicMock()
        resp.status = 403
        client.service.channels.return_value.list.return_value.execute.side_effect = HttpError(
            resp=resp, content=b"Forbidden"
        )
        YouTubeClient._channel_playlist_cache = {}

        result = client.resolve_channel_to_playlist("UC_forbidden")

        assert result is None


# ---------------------------------------------------------------------------
# TestYouTubeChannelIngestion
# ---------------------------------------------------------------------------


class TestYouTubeChannelIngestion:
    """Tests for YouTubeContentIngestionService.ingest_channels()."""

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(5),
    )
    async def test_resolves_and_ingests_channel(self, mock_ingest, mock_settings):
        """Channel source should be resolved to playlist and ingested."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubeChannelSource(channel_id="UC_test", name="Test Channel"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True
        service.client.resolve_channel_to_playlist = MagicMock(return_value="UU_test")

        response = await service.ingest_channels(sources=sources)
        total = response.items_ingested

        service.client.resolve_channel_to_playlist.assert_called_once_with("UC_test")
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args.kwargs["playlist_id"] == "UU_test"
        assert total == 5

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_skips_unresolvable_channel(self, mock_ingest, mock_settings):
        """Channel that can't be resolved should be skipped."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubeChannelSource(channel_id="UC_bad", name="Bad Channel"),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True
        service.client.resolve_channel_to_playlist = MagicMock(return_value=None)

        response = await service.ingest_channels(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_not_called()
        assert total == 0

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(3),
    )
    async def test_private_channel_skipped_without_oauth(self, mock_ingest, mock_settings):
        """Private channels are skipped when OAuth is unavailable."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubeChannelSource(
                channel_id="UC_priv", name="Private Channel", visibility="private"
            ),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = False

        response = await service.ingest_channels(sources=sources)
        total = response.items_ingested

        mock_ingest.assert_not_called()
        assert total == 0

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(2),
    )
    async def test_passes_channel_languages(self, mock_ingest, mock_settings):
        """Channel languages should be passed through to ingest_playlist."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubeChannelSource(channel_id="UC_lang", name="Lang Channel", languages=["de", "en"]),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True
        service.client.resolve_channel_to_playlist = MagicMock(return_value="UU_lang")

        await service.ingest_channels(sources=sources)

        assert mock_ingest.call_args.kwargs["languages"] == ["de", "en"]

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_per_channel_max_entries(self, mock_ingest, mock_settings):
        """Channel max_entries should override default max_videos_per_channel."""
        mock_settings.youtube_max_concurrent_playlists = 3
        sources = [
            YouTubeChannelSource(channel_id="UC_limited", name="Limited", max_entries=3),
        ]

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True
        service.client.resolve_channel_to_playlist = MagicMock(return_value="UU_limited")

        await service.ingest_channels(sources=sources, max_videos_per_channel=25)

        assert mock_ingest.call_args.kwargs["max_videos"] == 3

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch.object(
        YouTubeContentIngestionService,
        "ingest_playlist",
        new_callable=AsyncMock,
        side_effect=_yt_fetch_builder(1),
    )
    async def test_loads_channels_from_config(self, mock_ingest, mock_settings):
        """When no sources param, loads from SourcesConfig."""
        mock_settings.youtube_max_concurrent_playlists = 3
        mock_config = MagicMock()
        mock_config.get_youtube_channel_sources.return_value = [
            YouTubeChannelSource(channel_id="UC_config", name="Config Channel"),
        ]
        mock_settings.get_sources_config.return_value = mock_config

        service = YouTubeContentIngestionService()
        service.client.oauth_available = True
        service.client.resolve_channel_to_playlist = MagicMock(return_value="UU_config")

        response = await service.ingest_channels()
        total = response.items_ingested

        mock_settings.get_sources_config.assert_called_once()
        assert total == 1
