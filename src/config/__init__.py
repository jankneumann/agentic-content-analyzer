"""Configuration package for the newsletter aggregator.

Modules:
    config: Main application configuration (API keys, database URLs, etc.)
    models: LLM model configuration and provider management
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
]
