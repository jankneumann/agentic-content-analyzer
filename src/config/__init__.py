"""Configuration package for the newsletter aggregator.

Modules:
    config: Main application configuration (API keys, database URLs, etc.)
    models: LLM model configuration and provider management
    sources: Unified ingestion source configuration (sources.d/ YAML files)
"""

from src.config.models import (
    ModelConfig,
    ModelFamily,
    ModelStep,
    Provider,
    ProviderConfig,
    get_model_config,
    set_model_config,
)
from src.config.settings import Settings, get_settings, settings
from src.config.sources import (
    GmailSource,
    PodcastSource,
    RSSSource,
    Source,
    SourcesConfig,
    YouTubeChannelSource,
    YouTubePlaylistSource,
    YouTubeRSSSource,
    load_sources_config,
)

__all__ = [
    # Application settings
    "Settings",
    "get_settings",
    "settings",
    # Model configuration
    "ModelConfig",
    "ModelFamily",
    "ModelStep",
    "Provider",
    "ProviderConfig",
    "get_model_config",
    "set_model_config",
    # Source configuration
    "GmailSource",
    "PodcastSource",
    "RSSSource",
    "Source",
    "SourcesConfig",
    "YouTubeChannelSource",
    "YouTubePlaylistSource",
    "YouTubeRSSSource",
    "load_sources_config",
]
