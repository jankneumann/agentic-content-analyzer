"""Tests for unified source configuration models and loader."""

import pytest
import yaml

from src.config.sources import (
    GmailSource,
    PodcastSource,
    RSSSource,
    SourceDefaults,
    SourcesConfig,
    YouTubeChannelSource,
    YouTubePlaylistSource,
    YouTubeRSSSource,
    load_sources_config,
    load_sources_directory,
    load_sources_from_legacy,
    load_sources_yaml,
)

# --- Fixtures ---


@pytest.fixture
def tmp_sources_dir(tmp_path):
    """Create a temporary sources.d/ directory."""
    d = tmp_path / "sources.d"
    d.mkdir()
    return d


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with various config options."""
    return tmp_path


# --- Source Model Tests ---


class TestSourceModels:
    """Tests for individual source type Pydantic models."""

    def test_rss_source(self):
        s = RSSSource(url="https://example.com/feed")
        assert s.type == "rss"
        assert s.url == "https://example.com/feed"
        assert s.enabled is True
        assert s.tags == []
        assert s.name is None

    def test_rss_source_with_metadata(self):
        s = RSSSource(
            url="https://example.com/feed",
            name="Test Feed",
            tags=["ai", "ml"],
            max_entries=20,
            enabled=False,
        )
        assert s.name == "Test Feed"
        assert s.tags == ["ai", "ml"]
        assert s.max_entries == 20
        assert s.enabled is False

    def test_youtube_playlist_source(self):
        s = YouTubePlaylistSource(id="PLtest123")
        assert s.type == "youtube_playlist"
        assert s.id == "PLtest123"
        assert s.visibility == "public"

    def test_youtube_playlist_private(self):
        s = YouTubePlaylistSource(id="PLtest123", visibility="private")
        assert s.visibility == "private"

    def test_youtube_channel_source(self):
        s = YouTubeChannelSource(channel_id="UCtest123")
        assert s.type == "youtube_channel"
        assert s.channel_id == "UCtest123"
        assert s.visibility == "public"
        assert s.languages == ["en"]

    def test_youtube_rss_source(self):
        s = YouTubeRSSSource(url="https://www.youtube.com/feeds/videos.xml?channel_id=UCtest")
        assert s.type == "youtube_rss"

    def test_podcast_source(self):
        s = PodcastSource(url="https://feeds.example.com/podcast")
        assert s.type == "podcast"
        assert s.transcribe is True
        assert s.stt_provider == "openai"
        assert s.languages == ["en"]

    def test_podcast_source_no_transcribe(self):
        s = PodcastSource(url="https://feeds.example.com/podcast", transcribe=False)
        assert s.transcribe is False

    def test_gmail_source(self):
        s = GmailSource()
        assert s.type == "gmail"
        assert s.query == "label:newsletters-ai"
        assert s.max_results == 50

    def test_gmail_source_custom(self):
        s = GmailSource(query="label:tech", max_results=100)
        assert s.query == "label:tech"
        assert s.max_results == 100


class TestSourceDefaults:
    """Tests for the SourceDefaults model."""

    def test_default_values(self):
        d = SourceDefaults()
        assert d.type is None
        assert d.enabled is True
        assert d.max_entries == 10
        assert d.days_back == 7

    def test_type_default(self):
        d = SourceDefaults(type="rss")
        assert d.type == "rss"

    def test_exclude_unset(self):
        d = SourceDefaults(type="rss", max_entries=20)
        dumped = d.model_dump(exclude_unset=True)
        assert dumped == {"type": "rss", "max_entries": 20}
        assert "enabled" not in dumped


# --- SourcesConfig Tests ---


class TestSourcesConfig:
    """Tests for the merged SourcesConfig model."""

    def test_empty_config(self):
        config = SourcesConfig()
        assert config.version == 1
        assert config.sources == []

    def test_discriminated_union(self):
        """Sources list validates via type discriminator."""
        config = SourcesConfig(
            sources=[
                {"type": "rss", "url": "https://example.com/feed"},
                {"type": "youtube_playlist", "id": "PLtest"},
                {"type": "podcast", "url": "https://example.com/podcast"},
            ]
        )
        assert len(config.sources) == 3
        assert isinstance(config.sources[0], RSSSource)
        assert isinstance(config.sources[1], YouTubePlaylistSource)
        assert isinstance(config.sources[2], PodcastSource)

    def test_invalid_type_fails(self):
        """Unknown type should fail validation."""
        with pytest.raises(ValueError):
            SourcesConfig(sources=[{"type": "unknown_source", "url": "https://example.com"}])

    def test_missing_required_field_fails(self):
        """Missing required field should fail validation."""
        with pytest.raises(ValueError):
            SourcesConfig(
                sources=[{"type": "rss"}]  # Missing url
            )

    def test_get_sources_by_type(self):
        config = SourcesConfig(
            sources=[
                {"type": "rss", "url": "https://a.com/feed"},
                {"type": "rss", "url": "https://b.com/feed", "enabled": False},
                {"type": "podcast", "url": "https://c.com/feed"},
            ]
        )
        rss = config.get_rss_sources()
        assert len(rss) == 1
        assert rss[0].url == "https://a.com/feed"

    def test_get_youtube_playlist_sources(self):
        config = SourcesConfig(
            sources=[
                {"type": "youtube_playlist", "id": "PL1"},
                {"type": "youtube_playlist", "id": "PL2", "enabled": False},
                {"type": "youtube_playlist", "id": "PL3", "visibility": "private"},
            ]
        )
        playlists = config.get_youtube_playlist_sources()
        assert len(playlists) == 2
        assert playlists[0].id == "PL1"
        assert playlists[1].id == "PL3"
        assert playlists[1].visibility == "private"

    def test_get_podcast_sources(self):
        config = SourcesConfig(
            sources=[
                {"type": "podcast", "url": "https://feed1.com"},
                {"type": "podcast", "url": "https://feed2.com", "transcribe": False},
            ]
        )
        podcasts = config.get_podcast_sources()
        assert len(podcasts) == 2
        assert podcasts[0].transcribe is True
        assert podcasts[1].transcribe is False


# --- YAML File Loading Tests ---


class TestLoadSourcesYaml:
    """Tests for loading from a single sources.yaml file."""

    def test_load_basic_yaml(self, tmp_path):
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "defaults": {"max_entries": 5},
                    "sources": [
                        {"type": "rss", "url": "https://example.com/feed", "name": "Test"},
                    ],
                }
            )
        )
        config = load_sources_yaml(yaml_file)
        assert config.version == 1
        assert len(config.sources) == 1
        assert isinstance(config.sources[0], RSSSource)
        assert config.sources[0].name == "Test"

    def test_load_yaml_with_defaults(self, tmp_path):
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss", "tags": ["default-tag"]},
                    "sources": [
                        {"url": "https://a.com/feed"},
                        {"url": "https://b.com/feed", "tags": ["custom"]},
                    ],
                }
            )
        )
        config = load_sources_yaml(yaml_file)
        assert len(config.sources) == 2
        # First entry inherits type and tags from defaults
        assert config.sources[0].type == "rss"
        assert config.sources[0].tags == ["default-tag"]
        # Second entry overrides tags
        assert config.sources[1].tags == ["custom"]

    def test_load_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text("")
        config = load_sources_yaml(yaml_file)
        assert config.sources == []

    def test_load_invalid_yaml_raises(self, tmp_path):
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "sources": [{"type": "rss"}]  # Missing url
                }
            )
        )
        with pytest.raises(ValueError, match="validation failed"):
            load_sources_yaml(yaml_file)


# --- Directory Loading Tests ---


class TestLoadSourcesDirectory:
    """Tests for loading from sources.d/ directory."""

    def test_load_empty_directory(self, tmp_sources_dir):
        config = load_sources_directory(tmp_sources_dir)
        assert config.sources == []

    def test_load_single_file(self, tmp_sources_dir):
        rss_file = tmp_sources_dir / "rss.yaml"
        rss_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss"},
                    "sources": [
                        {"url": "https://a.com/feed", "name": "Feed A"},
                        {"url": "https://b.com/feed", "name": "Feed B"},
                    ],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        assert len(config.sources) == 2
        assert all(isinstance(s, RSSSource) for s in config.sources)

    def test_load_multiple_files_merged(self, tmp_sources_dir):
        """Sources from multiple files should be merged."""
        rss_file = tmp_sources_dir / "rss.yaml"
        rss_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss"},
                    "sources": [{"url": "https://a.com/feed"}],
                }
            )
        )
        yt_file = tmp_sources_dir / "youtube.yaml"
        yt_file.write_text(
            yaml.dump(
                {
                    "sources": [
                        {"type": "youtube_playlist", "id": "PLtest"},
                    ],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        assert len(config.sources) == 2
        assert isinstance(config.sources[0], RSSSource)
        assert isinstance(config.sources[1], YouTubePlaylistSource)

    def test_global_defaults_from_defaults_yaml(self, tmp_sources_dir):
        """_defaults.yaml provides global defaults applied to all files."""
        defaults_file = tmp_sources_dir / "_defaults.yaml"
        defaults_file.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "defaults": {"max_entries": 5, "enabled": True},
                }
            )
        )
        rss_file = tmp_sources_dir / "rss.yaml"
        rss_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss"},
                    "sources": [{"url": "https://a.com/feed"}],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        assert config.version == 2
        assert len(config.sources) == 1
        # max_entries inherited from global defaults
        assert config.sources[0].max_entries == 5

    def test_per_file_defaults_override_global(self, tmp_sources_dir):
        """Per-file defaults should override global defaults."""
        defaults_file = tmp_sources_dir / "_defaults.yaml"
        defaults_file.write_text(yaml.dump({"defaults": {"max_entries": 5, "tags": ["global"]}}))
        rss_file = tmp_sources_dir / "rss.yaml"
        rss_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss", "max_entries": 20},
                    "sources": [{"url": "https://a.com/feed"}],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        # max_entries overridden by file defaults
        assert config.sources[0].max_entries == 20
        # tags inherited from global since file didn't override
        assert config.sources[0].tags == ["global"]

    def test_entry_fields_override_all_defaults(self, tmp_sources_dir):
        """Per-entry fields should override both file and global defaults."""
        defaults_file = tmp_sources_dir / "_defaults.yaml"
        defaults_file.write_text(yaml.dump({"defaults": {"max_entries": 5}}))
        rss_file = tmp_sources_dir / "rss.yaml"
        rss_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss", "max_entries": 20},
                    "sources": [
                        {"url": "https://a.com/feed", "max_entries": 50},
                    ],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        assert config.sources[0].max_entries == 50

    def test_type_default_per_file(self, tmp_sources_dir):
        """Setting type in per-file defaults allows entries to omit type."""
        podcast_file = tmp_sources_dir / "podcasts.yaml"
        podcast_file.write_text(
            yaml.dump(
                {
                    "defaults": {"type": "podcast", "transcribe": True},
                    "sources": [
                        {"url": "https://feed1.com", "name": "Podcast 1"},
                        {"url": "https://feed2.com", "name": "Podcast 2", "transcribe": False},
                    ],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        assert len(config.sources) == 2
        assert all(isinstance(s, PodcastSource) for s in config.sources)
        assert config.sources[0].transcribe is True
        assert config.sources[1].transcribe is False

    def test_mixed_type_topic_file(self, tmp_sources_dir):
        """A topic file can mix source types without a type default."""
        topic_file = tmp_sources_dir / "ai-research.yaml"
        topic_file.write_text(
            yaml.dump(
                {
                    "sources": [
                        {"type": "rss", "url": "https://arxiv.org/rss/cs.AI", "name": "arXiv"},
                        {"type": "youtube_channel", "channel_id": "UCtest", "name": "AI Channel"},
                        {"type": "podcast", "url": "https://ai-podcast.com/feed", "name": "AI Pod"},
                    ],
                }
            )
        )
        config = load_sources_directory(tmp_sources_dir)
        assert len(config.sources) == 3
        assert isinstance(config.sources[0], RSSSource)
        assert isinstance(config.sources[1], YouTubeChannelSource)
        assert isinstance(config.sources[2], PodcastSource)

    def test_alphabetical_loading_order(self, tmp_sources_dir):
        """Files should be loaded in alphabetical order."""
        # Create files in reverse alphabetical order
        (tmp_sources_dir / "z_last.yaml").write_text(
            yaml.dump({"sources": [{"type": "rss", "url": "https://z.com/feed"}]})
        )
        (tmp_sources_dir / "a_first.yaml").write_text(
            yaml.dump({"sources": [{"type": "rss", "url": "https://a.com/feed"}]})
        )
        config = load_sources_directory(tmp_sources_dir)
        assert config.sources[0].url == "https://a.com/feed"
        assert config.sources[1].url == "https://z.com/feed"

    def test_invalid_entry_fails_fast(self, tmp_sources_dir):
        """Invalid entry should cause fail-fast (no partial loading)."""
        rss_file = tmp_sources_dir / "rss.yaml"
        rss_file.write_text(
            yaml.dump(
                {
                    "sources": [
                        {"type": "rss", "url": "https://valid.com/feed"},
                        {"type": "rss"},  # Missing url — should fail
                    ],
                }
            )
        )
        with pytest.raises(ValueError, match="validation failed"):
            load_sources_directory(tmp_sources_dir)

    def test_invalid_yaml_file_reports_filename(self, tmp_sources_dir):
        """Errors should include the filename for debugging."""
        bad_file = tmp_sources_dir / "broken.yaml"
        bad_file.write_text("invalid: yaml: [")
        with pytest.raises(ValueError, match="broken.yaml"):
            load_sources_directory(tmp_sources_dir)


# --- Legacy Fallback Tests ---


class TestLoadSourcesFromLegacy:
    """Tests for legacy config file loading."""

    def test_load_rss_feeds(self, tmp_path):
        rss_file = tmp_path / "rss_feeds.txt"
        rss_file.write_text(
            "# Comment line\n"
            "https://a.com/feed\n"
            "https://b.com/feed\n"
            "\n"  # Empty line
            "https://c.com/feed\n"
        )
        config = load_sources_from_legacy(
            rss_feeds_file=str(rss_file),
            youtube_playlists_file=str(tmp_path / "nonexistent.txt"),
        )
        assert len(config.sources) == 3
        assert all(isinstance(s, RSSSource) for s in config.sources)
        assert config.sources[0].url == "https://a.com/feed"

    def test_load_youtube_playlists(self, tmp_path):
        yt_file = tmp_path / "youtube_playlists.txt"
        yt_file.write_text("# Comment\nPLtest1 | Test playlist 1\nPLtest2\n")
        config = load_sources_from_legacy(
            rss_feeds_file=str(tmp_path / "nonexistent.txt"),
            youtube_playlists_file=str(yt_file),
        )
        assert len(config.sources) == 2
        assert all(isinstance(s, YouTubePlaylistSource) for s in config.sources)
        assert config.sources[0].id == "PLtest1"
        assert config.sources[0].name == "Test playlist 1"
        assert config.sources[1].id == "PLtest2"

    def test_load_both_legacy_files(self, tmp_path):
        rss_file = tmp_path / "rss_feeds.txt"
        rss_file.write_text("https://a.com/feed\n")
        yt_file = tmp_path / "youtube_playlists.txt"
        yt_file.write_text("PLtest1 | My Playlist\n")

        config = load_sources_from_legacy(
            rss_feeds_file=str(rss_file),
            youtube_playlists_file=str(yt_file),
        )
        assert len(config.sources) == 2
        assert isinstance(config.sources[0], RSSSource)
        assert isinstance(config.sources[1], YouTubePlaylistSource)

    def test_load_missing_files_returns_empty(self, tmp_path):
        config = load_sources_from_legacy(
            rss_feeds_file=str(tmp_path / "no_rss.txt"),
            youtube_playlists_file=str(tmp_path / "no_yt.txt"),
        )
        assert config.sources == []


# --- Three-Tier Resolution Tests ---


class TestLoadSourcesConfig:
    """Tests for the three-tier config resolution: dir → file → legacy."""

    def test_prefers_directory_over_file(self, tmp_path):
        """sources.d/ takes priority over sources.yaml."""
        # Create both
        sources_dir = tmp_path / "sources.d"
        sources_dir.mkdir()
        (sources_dir / "rss.yaml").write_text(
            yaml.dump({"sources": [{"type": "rss", "url": "https://from-dir.com/feed"}]})
        )
        sources_file = tmp_path / "sources.yaml"
        sources_file.write_text(
            yaml.dump({"sources": [{"type": "rss", "url": "https://from-file.com/feed"}]})
        )

        config = load_sources_config(
            sources_dir=str(sources_dir),
            sources_file=str(sources_file),
        )
        assert config.sources[0].url == "https://from-dir.com/feed"

    def test_falls_back_to_file(self, tmp_path):
        """When no sources.d/, uses sources.yaml."""
        sources_file = tmp_path / "sources.yaml"
        sources_file.write_text(
            yaml.dump({"sources": [{"type": "rss", "url": "https://from-file.com/feed"}]})
        )

        config = load_sources_config(
            sources_dir=str(tmp_path / "nonexistent_dir"),
            sources_file=str(sources_file),
        )
        assert config.sources[0].url == "https://from-file.com/feed"

    def test_falls_back_to_legacy(self, tmp_path):
        """When no dir or file, uses legacy txt files."""
        rss_file = tmp_path / "rss_feeds.txt"
        rss_file.write_text("https://legacy.com/feed\n")

        config = load_sources_config(
            sources_dir=str(tmp_path / "no_dir"),
            sources_file=str(tmp_path / "no_file.yaml"),
            rss_feeds_file=str(rss_file),
            youtube_playlists_file=str(tmp_path / "no_yt.txt"),
        )
        assert len(config.sources) == 1
        assert config.sources[0].url == "https://legacy.com/feed"

    def test_all_missing_returns_empty(self, tmp_path):
        """When nothing exists, returns empty config."""
        config = load_sources_config(
            sources_dir=str(tmp_path / "no_dir"),
            sources_file=str(tmp_path / "no_file.yaml"),
            rss_feeds_file=str(tmp_path / "no_rss.txt"),
            youtube_playlists_file=str(tmp_path / "no_yt.txt"),
        )
        assert config.sources == []


# --- Settings Integration Tests ---


class TestSettingsSourcesConfig:
    """Tests for Settings.get_sources_config() integration."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_settings_has_sources_config_fields(self):
        from src.config.settings import Settings

        s = Settings(_env_file=None, anthropic_api_key="test")
        assert s.sources_config_dir == "sources.d"
        assert s.sources_config_file == "sources.yaml"

    def test_settings_has_podcast_fields(self):
        from src.config.settings import Settings

        s = Settings(_env_file=None, anthropic_api_key="test")
        assert s.podcast_stt_provider == "openai"
        assert s.podcast_max_duration_minutes == 120
        assert s.podcast_temp_dir == "/tmp/podcast_downloads"  # noqa: S108

    def test_get_sources_config_returns_sources_config(self, tmp_path):
        from src.config.settings import Settings

        sources_file = tmp_path / "sources.yaml"
        sources_file.write_text(
            yaml.dump({"sources": [{"type": "rss", "url": "https://test.com/feed"}]})
        )
        s = Settings(
            _env_file=None,
            anthropic_api_key="test",
            sources_config_dir=str(tmp_path / "no_dir"),
            sources_config_file=str(sources_file),
        )
        config = s.get_sources_config()
        assert isinstance(config, SourcesConfig)
        assert len(config.sources) == 1


# --- Disabled Source Tests ---


class TestDisabledSources:
    """Tests for enabled/disabled source filtering."""

    def test_disabled_source_excluded_from_getters(self):
        config = SourcesConfig(
            sources=[
                {"type": "rss", "url": "https://a.com/feed", "enabled": True},
                {"type": "rss", "url": "https://b.com/feed", "enabled": False},
            ]
        )
        assert len(config.get_rss_sources()) == 1

    def test_disabled_source_still_in_sources_list(self):
        config = SourcesConfig(
            sources=[
                {"type": "rss", "url": "https://a.com/feed", "enabled": False},
            ]
        )
        assert len(config.sources) == 1
        assert config.sources[0].enabled is False


# --- Full Integration: Directory with All Types ---


class TestFullDirectoryIntegration:
    """End-to-end test with a realistic sources.d/ setup."""

    def test_realistic_sources_directory(self, tmp_sources_dir):
        # _defaults.yaml
        (tmp_sources_dir / "_defaults.yaml").write_text(
            yaml.dump(
                {
                    "version": 1,
                    "defaults": {"max_entries": 10, "days_back": 7, "enabled": True},
                }
            )
        )

        # rss.yaml
        (tmp_sources_dir / "rss.yaml").write_text(
            yaml.dump(
                {
                    "defaults": {"type": "rss"},
                    "sources": [
                        {"url": "https://a.com/feed", "name": "Feed A", "tags": ["ai"]},
                        {"url": "https://b.com/feed", "name": "Feed B", "enabled": False},
                    ],
                }
            )
        )

        # youtube.yaml
        (tmp_sources_dir / "youtube.yaml").write_text(
            yaml.dump(
                {
                    "sources": [
                        {
                            "type": "youtube_playlist",
                            "id": "PL1",
                            "name": "Public",
                            "visibility": "public",
                        },
                        {
                            "type": "youtube_playlist",
                            "id": "PL2",
                            "name": "Private",
                            "visibility": "private",
                        },
                        {"type": "youtube_channel", "channel_id": "UC1", "name": "Channel"},
                        {"type": "youtube_rss", "url": "https://yt.com/feed", "name": "YT RSS"},
                    ],
                }
            )
        )

        # podcasts.yaml
        (tmp_sources_dir / "podcasts.yaml").write_text(
            yaml.dump(
                {
                    "defaults": {"type": "podcast", "transcribe": True, "stt_provider": "openai"},
                    "sources": [
                        {"url": "https://pod1.com/feed", "name": "Pod 1"},
                        {"url": "https://pod2.com/feed", "name": "Pod 2", "transcribe": False},
                    ],
                }
            )
        )

        # gmail.yaml
        (tmp_sources_dir / "gmail.yaml").write_text(
            yaml.dump(
                {
                    "defaults": {"type": "gmail"},
                    "sources": [
                        {"query": "label:ai", "name": "AI Emails"},
                    ],
                }
            )
        )

        config = load_sources_directory(tmp_sources_dir)

        # Total sources
        assert len(config.sources) == 9

        # RSS: 2 total, 1 enabled
        assert len(config.get_rss_sources()) == 1

        # YouTube playlists: 2 total
        playlists = config.get_youtube_playlist_sources()
        assert len(playlists) == 2
        assert playlists[0].visibility == "public"
        assert playlists[1].visibility == "private"

        # YouTube channels: 1
        assert len(config.get_youtube_channel_sources()) == 1

        # YouTube RSS: 1
        assert len(config.get_youtube_rss_sources()) == 1

        # Podcasts: 2
        podcasts = config.get_podcast_sources()
        assert len(podcasts) == 2
        assert podcasts[0].transcribe is True
        assert podcasts[1].transcribe is False

        # Gmail: 1
        gmail = config.get_gmail_sources()
        assert len(gmail) == 1
        assert gmail[0].query == "label:ai"
