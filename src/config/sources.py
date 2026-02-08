"""Unified source configuration models and loader.

Loads ingestion source definitions from YAML config files in sources.d/
directory or a single sources.yaml file. Supports cascading defaults:
  _defaults.yaml globals → per-file defaults → per-entry fields

Source types: rss, youtube_playlist, youtube_channel, youtube_rss, podcast, gmail, substack
"""

import logging
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --- Source Default Models ---


class SourceDefaults(BaseModel):
    """Defaults that can be set globally (_defaults.yaml) or per file.

    Any field here can be overridden per source entry. When `type` is set,
    all entries in the file inherit that type unless they override it.
    """

    type: str | None = None
    enabled: bool = True
    max_entries: int = 10
    days_back: int = 7
    tags: list[str] = []
    # YouTube-specific defaults
    visibility: Literal["public", "private"] = "public"
    languages: list[str] = ["en"]
    gemini_summary: bool = True
    gemini_resolution: str = "default"
    proofread: bool = True
    hint_terms: list[str] = []
    # Podcast-specific defaults
    transcribe: bool = True
    stt_provider: Literal["openai", "local_whisper"] = "openai"


# --- Source Type Models ---


class SourceBase(BaseModel):
    """Base for all source definitions."""

    type: str
    name: str | None = None
    tags: list[str] = []
    enabled: bool = True
    max_entries: int | None = None


class RSSSource(SourceBase):
    type: Literal["rss"] = "rss"
    url: str


class YouTubePlaylistSource(SourceBase):
    type: Literal["youtube_playlist"] = "youtube_playlist"
    id: str
    visibility: Literal["public", "private"] = "public"
    hint_terms: list[str] = []
    proofread: bool = True
    gemini_summary: bool = True
    gemini_resolution: str = "default"


class YouTubeChannelSource(SourceBase):
    type: Literal["youtube_channel"] = "youtube_channel"
    channel_id: str
    visibility: Literal["public", "private"] = "public"
    languages: list[str] = ["en"]


class YouTubeRSSSource(SourceBase):
    type: Literal["youtube_rss"] = "youtube_rss"
    url: str
    gemini_summary: bool = True
    gemini_resolution: str = "low"


class PodcastSource(SourceBase):
    type: Literal["podcast"] = "podcast"
    url: str
    transcribe: bool = True
    stt_provider: Literal["openai", "local_whisper"] = "openai"
    languages: list[str] = ["en"]


class GmailSource(SourceBase):
    type: Literal["gmail"] = "gmail"
    query: str = "label:newsletters-ai"
    max_results: int = 50


class SubstackSource(SourceBase):
    type: Literal["substack"] = "substack"
    url: str


# Discriminated union for all source types
Source = Annotated[
    RSSSource
    | YouTubePlaylistSource
    | YouTubeChannelSource
    | YouTubeRSSSource
    | PodcastSource
    | GmailSource
    | SubstackSource,
    Field(discriminator="type"),
]


class SourcesConfig(BaseModel):
    """Merged config after loading all files."""

    version: int = 1
    defaults: SourceDefaults = SourceDefaults()
    sources: list[Source] = []

    def get_sources_by_type(self, source_type: str) -> list[Source]:
        """Get all enabled sources of a given type."""
        return [s for s in self.sources if s.type == source_type and s.enabled]

    def get_rss_sources(self) -> list[RSSSource]:
        """Get all enabled RSS sources."""
        return [s for s in self.sources if isinstance(s, RSSSource) and s.enabled]

    def get_youtube_playlist_sources(self) -> list[YouTubePlaylistSource]:
        """Get all enabled YouTube playlist sources."""
        return [s for s in self.sources if isinstance(s, YouTubePlaylistSource) and s.enabled]

    def get_youtube_channel_sources(self) -> list[YouTubeChannelSource]:
        """Get all enabled YouTube channel sources."""
        return [s for s in self.sources if isinstance(s, YouTubeChannelSource) and s.enabled]

    def get_youtube_rss_sources(self) -> list[YouTubeRSSSource]:
        """Get all enabled YouTube RSS sources."""
        return [s for s in self.sources if isinstance(s, YouTubeRSSSource) and s.enabled]

    def get_podcast_sources(self) -> list[PodcastSource]:
        """Get all enabled podcast sources."""
        return [s for s in self.sources if isinstance(s, PodcastSource) and s.enabled]

    def get_gmail_sources(self) -> list[GmailSource]:
        """Get all enabled Gmail sources."""
        return [s for s in self.sources if isinstance(s, GmailSource) and s.enabled]

    def get_substack_sources(self) -> list[SubstackSource]:
        """Get all enabled Substack sources."""
        return [s for s in self.sources if isinstance(s, SubstackSource) and s.enabled]


# --- Source File Model (per-file schema) ---


class SourceFileConfig(BaseModel):
    """Schema for each YAML file in sources.d/ or a single sources.yaml."""

    version: int | None = None
    defaults: SourceDefaults = SourceDefaults()
    sources: list[dict[str, Any]] = []


# --- Loader Functions ---


def _apply_defaults(
    raw_source: dict[str, Any],
    file_defaults: dict[str, Any],
    global_defaults: dict[str, Any],
) -> dict[str, Any]:
    """Apply cascading defaults to a raw source entry.

    Resolution order: global_defaults → file_defaults → entry fields
    (most specific wins).
    """
    merged = {**global_defaults, **file_defaults, **raw_source}
    return merged


def load_sources_from_file(file_path: Path) -> SourceFileConfig:
    """Load and parse a single YAML source config file."""
    with open(file_path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return SourceFileConfig()

    return SourceFileConfig.model_validate(raw)


def load_sources_directory(sources_dir: Path) -> SourcesConfig:
    """Load and merge all YAML files from a sources.d/ directory.

    Files are loaded alphabetically. `_defaults.yaml` is processed first
    (due to _ prefix sorting before letters) and provides global defaults.
    Per-file defaults override globals, and per-entry fields override both.

    Args:
        sources_dir: Path to the sources.d/ directory

    Returns:
        Merged SourcesConfig with all sources validated

    Raises:
        ValueError: If any source entry fails validation
    """
    global_defaults: dict[str, Any] = {}
    version = 1
    all_sources: list[dict[str, Any]] = []

    yaml_files = sorted(sources_dir.glob("*.yaml"))
    if not yaml_files:
        logger.warning(f"No YAML files found in {sources_dir}")
        return SourcesConfig()

    for yaml_file in yaml_files:
        try:
            file_config = load_sources_from_file(yaml_file)
        except Exception as e:
            raise ValueError(f"Error loading {yaml_file.name}: {e}") from e

        if yaml_file.name == "_defaults.yaml":
            global_defaults = file_config.defaults.model_dump(exclude_unset=True)
            if file_config.version is not None:
                version = file_config.version
            continue

        # Get per-file defaults (only explicitly set fields)
        file_defaults = file_config.defaults.model_dump(exclude_unset=True)

        for raw_source in file_config.sources:
            merged = _apply_defaults(raw_source, file_defaults, global_defaults)
            all_sources.append(merged)

    # Validate all merged entries via discriminated union
    try:
        config = SourcesConfig(version=version, sources=all_sources)
    except Exception as e:
        raise ValueError(f"Source validation failed: {e}") from e

    enabled_count = sum(1 for s in config.sources if s.enabled)
    logger.info(
        f"Loaded {len(config.sources)} sources from {sources_dir} ({enabled_count} enabled)"
    )
    return config


def load_sources_yaml(file_path: Path) -> SourcesConfig:
    """Load sources from a single sources.yaml file.

    Args:
        file_path: Path to sources.yaml

    Returns:
        SourcesConfig with all sources validated

    Raises:
        ValueError: If any source entry fails validation
    """
    try:
        file_config = load_sources_from_file(file_path)
    except Exception as e:
        raise ValueError(f"Error loading {file_path}: {e}") from e

    global_defaults = file_config.defaults.model_dump(exclude_unset=True)
    all_sources: list[dict[str, Any]] = []

    for raw_source in file_config.sources:
        merged = _apply_defaults(raw_source, {}, global_defaults)
        all_sources.append(merged)

    try:
        config = SourcesConfig(
            version=file_config.version or 1,
            sources=all_sources,
        )
    except Exception as e:
        raise ValueError(f"Source validation failed in {file_path}: {e}") from e

    enabled_count = sum(1 for s in config.sources if s.enabled)
    logger.info(f"Loaded {len(config.sources)} sources from {file_path} ({enabled_count} enabled)")
    return config


def load_sources_from_legacy(
    rss_feeds_file: str = "rss_feeds.txt",
    youtube_playlists_file: str = "youtube_playlists.txt",
) -> SourcesConfig:
    """Load sources from legacy config files (rss_feeds.txt + youtube_playlists.txt).

    This is the fallback when neither sources.d/ nor sources.yaml exist.
    Logs a warning recommending migration.

    Args:
        rss_feeds_file: Path to RSS feeds file
        youtube_playlists_file: Path to YouTube playlists file

    Returns:
        SourcesConfig constructed from legacy files
    """
    logger.warning(
        "No sources.d/ directory or sources.yaml found. "
        "Falling back to legacy config files. "
        "Run 'python -m src.config.migrate_sources --output-dir sources.d' to migrate."
    )

    sources: list[dict[str, Any]] = []

    # Load RSS feeds
    rss_path = Path(rss_feeds_file)
    if rss_path.exists():
        with open(rss_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    sources.append({"type": "rss", "url": line})
        logger.info(
            f"Loaded {sum(1 for s in sources if s['type'] == 'rss')} RSS feeds from {rss_feeds_file}"
        )

    # Load YouTube playlists
    yt_path = Path(youtube_playlists_file)
    if yt_path.exists():
        yt_count = 0
        with open(yt_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:
                    playlist_id, description = line.split("|", 1)
                    sources.append(
                        {
                            "type": "youtube_playlist",
                            "id": playlist_id.strip(),
                            "name": description.strip(),
                        }
                    )
                else:
                    sources.append(
                        {
                            "type": "youtube_playlist",
                            "id": line.strip(),
                        }
                    )
                yt_count += 1
        logger.info(f"Loaded {yt_count} YouTube playlists from {youtube_playlists_file}")

    return SourcesConfig(sources=sources)


def load_sources_config(
    sources_dir: str = "sources.d",
    sources_file: str = "sources.yaml",
    rss_feeds_file: str = "rss_feeds.txt",
    youtube_playlists_file: str = "youtube_playlists.txt",
) -> SourcesConfig:
    """Load source configuration with three-tier resolution.

    Resolution order:
    1. sources.d/ directory (if exists) — recommended for production
    2. sources.yaml (if exists) — simpler setups
    3. Legacy files (rss_feeds.txt + youtube_playlists.txt) — backward compat

    Args:
        sources_dir: Path to sources.d/ directory
        sources_file: Path to sources.yaml file
        rss_feeds_file: Path to legacy RSS feeds file
        youtube_playlists_file: Path to legacy YouTube playlists file

    Returns:
        SourcesConfig with validated sources
    """
    dir_path = Path(sources_dir)
    file_path = Path(sources_file)

    if dir_path.is_dir():
        logger.info(f"Loading sources from directory: {dir_path}")
        return load_sources_directory(dir_path)

    if file_path.is_file():
        logger.info(f"Loading sources from file: {file_path}")
        return load_sources_yaml(file_path)

    return load_sources_from_legacy(rss_feeds_file, youtube_playlists_file)
