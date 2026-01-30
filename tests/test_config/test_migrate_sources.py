"""Tests for the migrate_sources script.

Covers markdown parsing, legacy file conversion, deduplication,
output modes (directory vs single file), and round-trip integration.
"""

from pathlib import Path

import pytest
import yaml

from src.config.migrate_sources import (
    deduplicate_sources,
    migrate,
    parse_legacy_rss,
    parse_legacy_youtube,
    parse_markdown_file,
    write_sources_directory,
    write_sources_file,
)
from src.config.sources import (
    PodcastSource,
    RSSSource,
    load_sources_directory,
    load_sources_yaml,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def markdown_file(tmp_path: Path) -> Path:
    """Create a sample markdown file with RSS, podcast, and YouTube sections."""
    content = """\
# AI Newsletter Sources

## RSS News

- [The Batch](https://www.deeplearning.ai/the-batch/) - Weekly AI news (RSS feed: https://www.deeplearning.ai/the-batch/feed/)
- [Import AI](https://importai.substack.com) - AI policy and research (RSS feed: https://importai.substack.com/feed)
- [No RSS Entry](https://example.com/blog) - A blog without RSS feed URL

## Podcasts

- [Latent Space](https://www.latent.space/) - AI engineering podcast (RSS feed: https://api.substack.com/feed/podcast/1084089.rss)
- [Practical AI](https://changelog.com/practicalai) - ML in production (RSS feed: https://changelog.com/practicalai/feed)

## YouTube Videos

- [3Blue1Brown](https://www.youtube.com/c/3blue1brown) - Math visualizations (RSS feed: https://www.youtube.com/feeds/videos.xml?channel_id=UCYO_jab_esuFRV4b17AJtAw)
- [Two Minute Papers](https://www.youtube.com/@TwoMinutePapers) - Research summaries (RSS feed: https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg)
"""
    p = tmp_path / "sources.md"
    p.write_text(content)
    return p


@pytest.fixture
def legacy_rss_file(tmp_path: Path) -> Path:
    """Create a legacy rss_feeds.txt file."""
    content = """\
# RSS feed URLs
https://www.deeplearning.ai/the-batch/feed/
https://importai.substack.com/feed
https://unique-legacy.com/feed
"""
    p = tmp_path / "rss_feeds.txt"
    p.write_text(content)
    return p


@pytest.fixture
def legacy_youtube_file(tmp_path: Path) -> Path:
    """Create a legacy youtube_playlists.txt file."""
    content = """\
# YouTube playlists
PLZHQObOWTQDPHP40bzkb0TKLRPw0GammP | Neural networks playlist
PLtest123
"""
    p = tmp_path / "youtube_playlists.txt"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Markdown Parsing Tests
# ---------------------------------------------------------------------------


class TestParseMarkdownFile:
    """Tests for parse_markdown_file() which extracts sources from markdown."""

    def test_parse_rss_entries(self, markdown_file: Path):
        result = parse_markdown_file(markdown_file)
        rss_sources = result["rss"]
        assert len(rss_sources) >= 2
        # Check the first RSS entry has both name and URL
        batch = next(s for s in rss_sources if "deeplearning" in s.get("url", ""))
        assert batch["name"] == "The Batch"
        assert batch["url"] == "https://www.deeplearning.ai/the-batch/feed/"
        assert batch["type"] == "rss"

    def test_parse_rss_entry_with_description(self, markdown_file: Path):
        result = parse_markdown_file(markdown_file)
        rss_sources = result["rss"]
        import_ai = next(s for s in rss_sources if "importai" in s.get("url", ""))
        assert import_ai["name"] == "Import AI"

    def test_parse_podcast_entries(self, markdown_file: Path):
        result = parse_markdown_file(markdown_file)
        podcasts = result["podcasts"]
        assert len(podcasts) == 2
        latent = next(s for s in podcasts if s.get("name") == "Latent Space")
        assert latent["type"] == "podcast"
        assert latent["name"] == "Latent Space"
        assert latent["url"] == "https://api.substack.com/feed/podcast/1084089.rss"
        # Podcasts from markdown should default to transcribe: false
        assert latent.get("transcribe") is False

    def test_parse_podcast_transcribe_false(self, markdown_file: Path):
        """All podcast entries parsed from markdown should have transcribe: false."""
        result = parse_markdown_file(markdown_file)
        for podcast in result["podcasts"]:
            assert podcast.get("transcribe") is False

    def test_parse_youtube_entries(self, markdown_file: Path):
        result = parse_markdown_file(markdown_file)
        youtube = result["youtube_rss"]
        assert len(youtube) == 2
        three_blue = next(s for s in youtube if "3Blue1Brown" in s.get("name", ""))
        assert three_blue["type"] == "youtube_rss"
        assert three_blue["name"] == "3Blue1Brown"
        assert "channel_id=UCYO_jab_esuFRV4b17AJtAw" in three_blue["url"]

    def test_entries_without_rss_url(self, markdown_file: Path):
        """Entries without '(RSS feed: ...)' should still be parsed."""
        result = parse_markdown_file(markdown_file)
        rss_sources = result["rss"]
        no_rss = [s for s in rss_sources if s.get("name") == "No RSS Entry"]
        # Entry without RSS feed URL should use the link URL as fallback
        # or be included with the link URL
        assert len(no_rss) == 1
        assert "example.com" in no_rss[0]["url"]

    def test_entries_without_description(self, tmp_path: Path):
        """Entries with no description text between link and RSS feed."""
        content = """\
## RSS News

- [Bare Link](https://example.com) (RSS feed: https://example.com/feed)
"""
        p = tmp_path / "bare.md"
        p.write_text(content)
        result = parse_markdown_file(p)
        rss_sources = result["rss"]
        assert len(rss_sources) == 1
        assert rss_sources[0]["name"] == "Bare Link"
        assert rss_sources[0]["url"] == "https://example.com/feed"

    def test_empty_file(self, tmp_path: Path):
        """Empty markdown file returns empty lists."""
        p = tmp_path / "empty.md"
        p.write_text("")
        result = parse_markdown_file(p)
        assert result["rss"] == []
        assert result["podcasts"] == []
        assert result["youtube_rss"] == []

    def test_no_sections(self, tmp_path: Path):
        """Markdown with no recognized sections returns empty lists."""
        content = "# Unrelated Document\n\nJust some text.\n"
        p = tmp_path / "nosections.md"
        p.write_text(content)
        result = parse_markdown_file(p)
        assert result["rss"] == []
        assert result["podcasts"] == []
        assert result["youtube_rss"] == []

    def test_rss_entry_format_variants(self, tmp_path: Path):
        """Handle slight variations in markdown entry format."""
        content = """\
## RSS News

- [Name Only](https://example.com/site) (RSS feed: https://example.com/feed)
- [With Dash Desc](https://example.com/site2) - Some description (RSS feed: https://example.com/feed2)
"""
        p = tmp_path / "variants.md"
        p.write_text(content)
        result = parse_markdown_file(p)
        rss_sources = result["rss"]
        assert len(rss_sources) == 2
        assert rss_sources[0]["name"] == "Name Only"
        assert rss_sources[0]["url"] == "https://example.com/feed"
        assert rss_sources[1]["name"] == "With Dash Desc"
        assert rss_sources[1]["url"] == "https://example.com/feed2"


# ---------------------------------------------------------------------------
# Legacy File Conversion Tests
# ---------------------------------------------------------------------------


class TestParseLegacyRss:
    """Tests for parse_legacy_rss() which reads rss_feeds.txt."""

    def test_parse_urls(self, legacy_rss_file: Path):
        sources = parse_legacy_rss(legacy_rss_file)
        assert len(sources) == 3
        assert all(s["type"] == "rss" for s in sources)
        urls = [s["url"] for s in sources]
        assert "https://www.deeplearning.ai/the-batch/feed/" in urls
        assert "https://importai.substack.com/feed" in urls
        assert "https://unique-legacy.com/feed" in urls

    def test_skip_comments(self, tmp_path: Path):
        p = tmp_path / "rss.txt"
        p.write_text("# comment\nhttps://valid.com/feed\n# another comment\n")
        sources = parse_legacy_rss(p)
        assert len(sources) == 1

    def test_skip_empty_lines(self, tmp_path: Path):
        p = tmp_path / "rss.txt"
        p.write_text("\n\nhttps://valid.com/feed\n\n")
        sources = parse_legacy_rss(p)
        assert len(sources) == 1

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "rss.txt"
        p.write_text("")
        sources = parse_legacy_rss(p)
        assert sources == []

    def test_whitespace_stripped(self, tmp_path: Path):
        p = tmp_path / "rss.txt"
        p.write_text("  https://valid.com/feed  \n")
        sources = parse_legacy_rss(p)
        assert sources[0]["url"] == "https://valid.com/feed"


class TestParseLegacyYoutube:
    """Tests for parse_legacy_youtube() which reads youtube_playlists.txt."""

    def test_parse_with_description(self, legacy_youtube_file: Path):
        sources = parse_legacy_youtube(legacy_youtube_file)
        assert len(sources) == 2
        described = next(s for s in sources if "PLZHQObOWTQDPHP40bzkb0TKLRPw0GammP" in s["id"])
        assert described["name"] == "Neural networks playlist"
        assert described["type"] == "youtube_playlist"

    def test_parse_without_description(self, legacy_youtube_file: Path):
        sources = parse_legacy_youtube(legacy_youtube_file)
        plain = next(s for s in sources if s["id"] == "PLtest123")
        assert plain["type"] == "youtube_playlist"
        assert plain.get("name") is None or plain["name"] == ""

    def test_skip_comments_and_blanks(self, tmp_path: Path):
        p = tmp_path / "yt.txt"
        p.write_text("# playlists\n\nPLtest1 | desc\n\n")
        sources = parse_legacy_youtube(p)
        assert len(sources) == 1

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "yt.txt"
        p.write_text("")
        sources = parse_legacy_youtube(p)
        assert sources == []

    def test_pipe_in_description(self, tmp_path: Path):
        """If description itself contains a pipe, only split on the first one."""
        p = tmp_path / "yt.txt"
        p.write_text("PLabc | desc with | pipe\n")
        sources = parse_legacy_youtube(p)
        assert sources[0]["id"] == "PLabc"
        assert sources[0]["name"] == "desc with | pipe"


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------


class TestDeduplicateSources:
    """Tests for deduplicate_sources() which merges duplicate entries."""

    def test_same_rss_url_keeps_richest_metadata(self):
        """When same URL appears in legacy and markdown, keep richest entry."""
        sources = [
            {"type": "rss", "url": "https://example.com/feed"},
            {"type": "rss", "url": "https://example.com/feed", "name": "Example Feed"},
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1
        assert result[0]["name"] == "Example Feed"

    def test_different_urls_not_deduplicated(self):
        sources = [
            {"type": "rss", "url": "https://a.com/feed", "name": "A"},
            {"type": "rss", "url": "https://b.com/feed", "name": "B"},
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 2

    def test_duplicate_urls_within_same_section(self):
        """Duplicate URLs in the same section should keep first occurrence."""
        sources = [
            {"type": "rss", "url": "https://dup.com/feed", "name": "First"},
            {"type": "rss", "url": "https://dup.com/feed", "name": "Second"},
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1
        # The one with name should be kept (richest metadata)
        assert result[0]["name"] in ("First", "Second")

    def test_dedup_preserves_order(self):
        """Non-duplicate entries should maintain their original order."""
        sources = [
            {"type": "rss", "url": "https://first.com/feed", "name": "First"},
            {"type": "rss", "url": "https://second.com/feed", "name": "Second"},
            {"type": "rss", "url": "https://third.com/feed", "name": "Third"},
        ]
        result = deduplicate_sources(sources)
        assert [s["name"] for s in result] == ["First", "Second", "Third"]

    def test_dedup_across_types_by_url(self):
        """Podcast and RSS with same URL should still be separate (different types)."""
        sources = [
            {"type": "rss", "url": "https://shared.com/feed", "name": "RSS"},
            {"type": "podcast", "url": "https://shared.com/feed", "name": "Podcast"},
        ]
        result = deduplicate_sources(sources)
        # Different types should not be deduplicated
        assert len(result) == 2

    def test_dedup_empty_list(self):
        assert deduplicate_sources([]) == []

    def test_dedup_single_entry(self):
        sources = [{"type": "rss", "url": "https://only.com/feed"}]
        result = deduplicate_sources(sources)
        assert len(result) == 1

    def test_dedup_prefers_entry_with_name(self):
        """When deduplicating, prefer the entry that has a name."""
        sources = [
            {"type": "rss", "url": "https://example.com/feed"},
            {"type": "rss", "url": "https://example.com/feed", "name": "Named"},
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1
        assert result[0].get("name") == "Named"


# ---------------------------------------------------------------------------
# Output Mode Tests
# ---------------------------------------------------------------------------


class TestWriteSourcesDirectory:
    """Tests for write_sources_directory() which creates split YAML files."""

    def test_creates_defaults_file(self, tmp_path: Path):
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed", "name": "A"}],
            "podcasts": [],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        defaults_file = output_dir / "_defaults.yaml"
        assert defaults_file.exists()
        data = yaml.safe_load(defaults_file.read_text())
        assert "version" in data
        assert "defaults" in data

    def test_creates_rss_yaml(self, tmp_path: Path):
        sources = {
            "rss": [
                {"type": "rss", "url": "https://a.com/feed", "name": "Feed A"},
                {"type": "rss", "url": "https://b.com/feed", "name": "Feed B"},
            ],
            "podcasts": [],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        rss_file = output_dir / "rss.yaml"
        assert rss_file.exists()
        data = yaml.safe_load(rss_file.read_text())
        assert "sources" in data
        assert len(data["sources"]) == 2

    def test_creates_youtube_yaml(self, tmp_path: Path):
        sources = {
            "rss": [],
            "podcasts": [],
            "youtube_rss": [
                {"type": "youtube_rss", "url": "https://yt.com/feed", "name": "Channel"},
            ],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        yt_file = output_dir / "youtube.yaml"
        assert yt_file.exists()
        data = yaml.safe_load(yt_file.read_text())
        assert len(data["sources"]) == 1
        assert data["sources"][0]["type"] == "youtube_rss"

    def test_creates_podcasts_yaml(self, tmp_path: Path):
        sources = {
            "rss": [],
            "podcasts": [
                {
                    "type": "podcast",
                    "url": "https://pod.com/feed",
                    "name": "Pod",
                    "transcribe": False,
                },
            ],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        pod_file = output_dir / "podcasts.yaml"
        assert pod_file.exists()
        data = yaml.safe_load(pod_file.read_text())
        assert len(data["sources"]) == 1
        # Type is set via file defaults, so entries may not have it inline
        assert (
            data.get("defaults", {}).get("type") == "podcast"
            or data["sources"][0].get("type") == "podcast"
        )

    def test_skips_empty_sections(self, tmp_path: Path):
        """Files should not be created for sections with no entries."""
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed"}],
            "podcasts": [],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        assert (output_dir / "rss.yaml").exists()
        assert not (output_dir / "podcasts.yaml").exists()
        assert not (output_dir / "youtube.yaml").exists()

    def test_yaml_output_is_valid(self, tmp_path: Path):
        """All generated YAML files should be valid and parseable."""
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed", "name": "A"}],
            "podcasts": [
                {
                    "type": "podcast",
                    "url": "https://pod.com/feed",
                    "name": "Pod",
                    "transcribe": False,
                }
            ],
            "youtube_rss": [{"type": "youtube_rss", "url": "https://yt.com/feed", "name": "YT"}],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        for yaml_file in output_dir.glob("*.yaml"):
            data = yaml.safe_load(yaml_file.read_text())
            assert data is not None


class TestWriteSourcesFile:
    """Tests for write_sources_file() which creates a single merged YAML."""

    def test_creates_single_file(self, tmp_path: Path):
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed", "name": "A"}],
            "podcasts": [
                {
                    "type": "podcast",
                    "url": "https://pod.com/feed",
                    "name": "Pod",
                    "transcribe": False,
                }
            ],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_file = tmp_path / "sources.yaml"
        write_sources_file(sources, output_file)

        assert output_file.exists()
        data = yaml.safe_load(output_file.read_text())
        assert "version" in data
        assert "sources" in data
        assert len(data["sources"]) == 2

    def test_single_file_combines_all_types(self, tmp_path: Path):
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed"}],
            "podcasts": [{"type": "podcast", "url": "https://pod.com/feed", "transcribe": False}],
            "youtube_rss": [{"type": "youtube_rss", "url": "https://yt.com/feed"}],
            "youtube_playlists": [{"type": "youtube_playlist", "id": "PLtest"}],
        }
        output_file = tmp_path / "sources.yaml"
        write_sources_file(sources, output_file)

        data = yaml.safe_load(output_file.read_text())
        types = {s["type"] for s in data["sources"]}
        assert "rss" in types
        assert "podcast" in types
        assert "youtube_rss" in types
        assert "youtube_playlist" in types

    def test_empty_sources_still_valid(self, tmp_path: Path):
        sources = {
            "rss": [],
            "podcasts": [],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_file = tmp_path / "sources.yaml"
        write_sources_file(sources, output_file)

        data = yaml.safe_load(output_file.read_text())
        assert data["sources"] == [] or "sources" in data


# ---------------------------------------------------------------------------
# Output Loadability Tests
# ---------------------------------------------------------------------------


class TestOutputLoadability:
    """Verify that YAML output is loadable by the existing loaders."""

    def test_directory_output_loadable(self, tmp_path: Path):
        """Output from write_sources_directory can be loaded by load_sources_directory."""
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed", "name": "Feed A"}],
            "podcasts": [
                {
                    "type": "podcast",
                    "url": "https://pod.com/feed",
                    "name": "Pod",
                    "transcribe": False,
                },
            ],
            "youtube_rss": [
                {
                    "type": "youtube_rss",
                    "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest",
                    "name": "YT Channel",
                },
            ],
            "youtube_playlists": [],
        }
        output_dir = tmp_path / "sources.d"
        output_dir.mkdir()
        write_sources_directory(sources, output_dir)

        config = load_sources_directory(output_dir)
        # 3 explicit sources + 1 gmail template = 4
        assert len(config.sources) >= 3

        rss = config.get_rss_sources()
        assert len(rss) == 1
        assert rss[0].url == "https://a.com/feed"

        pods = config.get_podcast_sources()
        assert len(pods) == 1
        assert pods[0].transcribe is False

        yt = config.get_youtube_rss_sources()
        assert len(yt) == 1
        assert "UCtest" in yt[0].url

    def test_single_file_output_loadable(self, tmp_path: Path):
        """Output from write_sources_file can be loaded by load_sources_yaml."""
        sources = {
            "rss": [{"type": "rss", "url": "https://a.com/feed", "name": "Feed A"}],
            "podcasts": [
                {
                    "type": "podcast",
                    "url": "https://pod.com/feed",
                    "name": "Pod",
                    "transcribe": False,
                },
            ],
            "youtube_rss": [],
            "youtube_playlists": [],
        }
        output_file = tmp_path / "sources.yaml"
        write_sources_file(sources, output_file)

        config = load_sources_yaml(output_file)
        assert len(config.sources) == 2
        assert isinstance(config.sources[0], RSSSource)
        assert isinstance(config.sources[1], PodcastSource)


# ---------------------------------------------------------------------------
# Integration / Round-Trip Tests
# ---------------------------------------------------------------------------


class TestMigrateIntegration:
    """Integration tests for the migrate() entry point."""

    def test_migrate_markdown_to_directory(self, markdown_file: Path, tmp_path: Path):
        """Round-trip: parse markdown -> output directory -> load -> verify."""
        output_dir = tmp_path / "output_sources.d"
        output_dir.mkdir()

        migrate(
            markdown_file=str(markdown_file),
            output_dir=str(output_dir),
        )

        config = load_sources_directory(output_dir)
        assert len(config.sources) > 0

        rss = config.get_rss_sources()
        assert any("deeplearning" in s.url for s in rss)

        podcasts = config.get_podcast_sources()
        assert len(podcasts) >= 1
        assert all(s.transcribe is False for s in podcasts)

        yt = config.get_youtube_rss_sources()
        assert len(yt) >= 1

    def test_migrate_markdown_to_single_file(self, markdown_file: Path, tmp_path: Path):
        """Round-trip: parse markdown -> single file -> load -> verify."""
        output_file = tmp_path / "sources.yaml"

        migrate(
            markdown_file=str(markdown_file),
            output=str(output_file),
        )

        config = load_sources_yaml(output_file)
        assert len(config.sources) > 0

    def test_migrate_with_legacy_files(
        self, markdown_file: Path, legacy_rss_file: Path, legacy_youtube_file: Path, tmp_path: Path
    ):
        """Migration merges markdown and legacy files, deduplicating."""
        output_dir = tmp_path / "merged_sources.d"
        output_dir.mkdir()

        migrate(
            markdown_file=str(markdown_file),
            legacy_rss_file=str(legacy_rss_file),
            legacy_youtube_file=str(legacy_youtube_file),
            output_dir=str(output_dir),
        )

        config = load_sources_directory(output_dir)

        # Legacy rss_feeds.txt had 3 URLs, 2 overlap with markdown
        # After dedup, we should have the markdown entries (richer) plus unique legacy
        rss = config.get_rss_sources()
        rss_urls = [s.url for s in rss]
        # unique-legacy.com should be present from legacy file
        assert any("unique-legacy.com" in u for u in rss_urls)
        # Deduplicated entries should have names from markdown
        batch = [s for s in rss if "deeplearning" in s.url]
        if batch:
            assert batch[0].name == "The Batch"

    def test_migrate_legacy_only(
        self, legacy_rss_file: Path, legacy_youtube_file: Path, tmp_path: Path
    ):
        """Migration works with only legacy files (no markdown)."""
        output_file = tmp_path / "sources.yaml"

        migrate(
            legacy_rss_file=str(legacy_rss_file),
            legacy_youtube_file=str(legacy_youtube_file),
            output=str(output_file),
        )

        config = load_sources_yaml(output_file)
        assert len(config.sources) > 0
        # Should have RSS and YouTube playlist entries
        types = {s.type for s in config.sources}
        assert "rss" in types
        assert "youtube_playlist" in types

    def test_round_trip_preserves_source_count(self, markdown_file: Path, tmp_path: Path):
        """Number of unique sources should be preserved across round-trip."""
        parsed = parse_markdown_file(markdown_file)
        total_parsed = len(parsed["rss"]) + len(parsed["podcasts"]) + len(parsed["youtube_rss"])

        output_dir = tmp_path / "rt_sources.d"
        output_dir.mkdir()
        migrate(markdown_file=str(markdown_file), output_dir=str(output_dir))

        config = load_sources_directory(output_dir)
        # Directory mode adds a gmail.yaml template with 1 default source
        non_gmail = [s for s in config.sources if s.type != "gmail"]
        assert len(non_gmail) == total_parsed

    def test_round_trip_source_types_match(self, markdown_file: Path, tmp_path: Path):
        """Source types should be preserved across round-trip."""
        parsed = parse_markdown_file(markdown_file)

        output_dir = tmp_path / "types_sources.d"
        output_dir.mkdir()
        migrate(markdown_file=str(markdown_file), output_dir=str(output_dir))

        config = load_sources_directory(output_dir)

        assert len(config.get_rss_sources()) == len(parsed["rss"])
        assert len(config.get_podcast_sources()) == len(parsed["podcasts"])
        assert len(config.get_youtube_rss_sources()) == len(parsed["youtube_rss"])
