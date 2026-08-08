"""Tests for Source API endpoint.

Tests the GET /api/v1/sources endpoint that returns configured
sources and content counts from the database.
"""

from unittest.mock import patch

from src.config.sources import (
    PodcastSource,
    ReadwiseSource,
    RSSSource,
    SourcesConfig,
    YouTubePlaylistSource,
)


class TestListSources:
    """Tests for GET /api/v1/sources endpoint."""

    def test_returns_empty_when_no_sources_configured(self, client):
        """Empty config returns empty sources list with zero counts."""
        empty_config = SourcesConfig(sources=[])

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_sources_config.return_value = empty_config
            response = client.get("/api/v1/sources")

        assert response.status_code == 200
        data = response.json()
        assert data["sources"] == []
        assert data["counts"] == {}
        assert data["total_sources"] == 0
        assert data["enabled_sources"] == 0

    def test_returns_configured_sources(self, client):
        """Sources from config are returned with correct type and metadata."""
        config = SourcesConfig(
            sources=[
                RSSSource(url="https://example.com/feed.xml", name="Example Feed", tags=["ai"]),
                PodcastSource(
                    url="https://example.com/podcast.xml",
                    name="AI Podcast",
                    tags=["ai", "podcast"],
                ),
            ]
        )

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_sources_config.return_value = config
            response = client.get("/api/v1/sources")

        assert response.status_code == 200
        data = response.json()
        assert data["total_sources"] == 2
        assert data["enabled_sources"] == 2

        # Check RSS source
        rss_source = data["sources"][0]
        assert rss_source["type"] == "rss"
        assert rss_source["name"] == "Example Feed"
        assert rss_source["url"] == "https://example.com/feed.xml"
        assert rss_source["enabled"] is True
        assert rss_source["tags"] == ["ai"]

        # Check Podcast source
        podcast_source = data["sources"][1]
        assert podcast_source["type"] == "podcast"
        assert podcast_source["name"] == "AI Podcast"

    def test_disabled_sources_not_counted_as_enabled(self, client):
        """Disabled sources are listed but not counted as enabled."""
        config = SourcesConfig(
            sources=[
                RSSSource(url="https://example.com/feed.xml", name="Active", enabled=True),
                RSSSource(url="https://example.com/feed2.xml", name="Inactive", enabled=False),
            ]
        )

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_sources_config.return_value = config
            response = client.get("/api/v1/sources")

        assert response.status_code == 200
        data = response.json()
        assert data["total_sources"] == 2
        assert data["enabled_sources"] == 1

    def test_youtube_playlist_url_format(self, client):
        """YouTube playlist sources show full playlist URL."""
        config = SourcesConfig(
            sources=[
                YouTubePlaylistSource(id="PLabc123", name="AI Playlist"),
            ]
        )

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_sources_config.return_value = config
            response = client.get("/api/v1/sources")

        assert response.status_code == 200
        data = response.json()
        playlist_source = data["sources"][0]
        assert playlist_source["type"] == "youtube_playlist"
        assert playlist_source["url"] == "https://www.youtube.com/playlist?list=PLabc123"

    def test_readwise_source_uses_stable_default_locator(self, client):
        """Singleton sources without URLs expose their canonical locator."""
        config = SourcesConfig(sources=[ReadwiseSource()])

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_sources_config.return_value = config
            response = client.get("/api/v1/sources")

        assert response.status_code == 200
        readwise_source = response.json()["sources"][0]
        assert readwise_source["url"] == "default"
        assert readwise_source["source_key"] == "readwise:default"

    def test_obsidian_source_projection_is_opaque_and_path_free(self):
        from src.api.source_routes import project_source_info

        private_path = "/Users/alice/Library/Mobile Documents/private-vault"
        private_folder = "Clients/Acquisition"
        secret_label = "Board research vault"

        class ObsidianSource:
            type = "obsidian_vault"
            vault_id = "board-research"
            vault_path = private_path
            ingest_folder = private_folder
            name = secret_label
            tags = ("private-client",)
            enabled = True
            origin = "db"

            def model_dump(self):
                return {
                    "type": self.type,
                    "vault_id": self.vault_id,
                    "vault_path": self.vault_path,
                    "ingest_folder": self.ingest_folder,
                    "name": self.name,
                    "tags": self.tags,
                    "enabled": self.enabled,
                    "origin": self.origin,
                }

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_configured_source_key_secret.return_value = (
                "configured-source-key-secret-for-tests"
            )
            source = project_source_info(ObsidianSource()).model_dump(mode="json")

        assert source["source_key"].startswith("src_")
        assert source["url"] == source["source_key"]
        assert source["name"] is None
        assert source["tags"] == []
        serialized = str(source)
        for private_value in (
            private_path,
            private_folder,
            secret_label,
            "board-research",
            "private-client",
        ):
            assert private_value not in serialized

    def test_includes_content_counts(self, client, sample_contents):
        """Content counts from database are included in response."""
        config = SourcesConfig(sources=[])

        with patch("src.api.source_routes.settings") as mock_settings:
            mock_settings.get_sources_config.return_value = config
            response = client.get("/api/v1/sources")

        assert response.status_code == 200
        data = response.json()
        counts = data["counts"]
        # sample_contents fixture has 1 gmail, 1 rss, 1 youtube
        assert counts.get("gmail", 0) == 1
        assert counts.get("rss", 0) == 1
        assert counts.get("youtube", 0) == 1
