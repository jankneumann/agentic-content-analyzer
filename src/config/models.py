"""Model configuration for LLM selection and cost tracking.

This module provides centralized configuration for:
- Model selection per pipeline step (summarization, theme analysis, etc.)
- Multi-cloud provider support (Anthropic, AWS Bedrock, Vertex AI, Azure, OpenAI)
- Provider failover (automatic fallback if rate limited)
- Provider-specific pricing and limits (loaded from YAML config)
- Cost tracking and estimation
- Framework flexibility

Architecture:
    Model: The LLM itself (e.g., "claude-sonnet-4-5-20251022")
    Provider: Where to access it (Anthropic API, AWS Bedrock, Vertex AI, etc.)
    ProviderConfig: Provider + API credentials + settings
    ProviderModelConfig: Provider-specific settings for a model (cost, limits, tier)
    ModelConfig: Which model to use for each pipeline step + provider preferences

Configuration is loaded from src/config/model_registry.yaml for easy updates.

Usage:
    from src.config.models import get_model_config, ModelStep, ProviderConfig, Provider

    # Get global config
    config = get_model_config()

    # Get model for a step
    model_id = config.get_model_for_step(ModelStep.SUMMARIZATION)

    # Get providers for a model (in priority order for failover)
    providers = config.get_providers_for_model(model_id)

    # Calculate cost (provider-specific)
    cost = config.calculate_cost(
        model_id,
        provider=Provider.AWS_BEDROCK,
        input_tokens=1000,
        output_tokens=500
    )

    # Estimate monthly costs
    estimate = config.get_cost_estimate(
        newsletters_per_day=10,
        digests_per_week=2
    )
"""

import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class Provider(StrEnum):
    """LLM provider/platform."""

    ANTHROPIC = "anthropic"  # Anthropic API (direct)
    AWS_BEDROCK = "aws_bedrock"  # AWS Bedrock
    GOOGLE_VERTEX = "google_vertex"  # Google Vertex AI
    MICROSOFT_AZURE = "microsoft_azure"  # Microsoft Azure OpenAI
    OPENAI = "openai"  # OpenAI API (direct)
    GOOGLE_AI = "google_ai"  # Google AI Studio (direct)


class ModelFamily(StrEnum):
    """Model family (across providers)."""

    CLAUDE = "claude"
    GEMINI = "gemini"
    GPT = "gpt"
    WHISPER = "whisper"  # OpenAI Whisper (STT-only)
    DEEPGRAM = "deepgram"  # Deepgram (STT-only)


class ModelStep(StrEnum):
    """Pipeline steps that use LLMs."""

    SUMMARIZATION = "summarization"  # Individual content summarization
    THEME_ANALYSIS = "theme_analysis"  # Cross-content theme extraction
    DIGEST_CREATION = "digest_creation"  # Digest generation
    DIGEST_REVISION = "digest_revision"  # Interactive digest revision
    HISTORICAL_CONTEXT = "historical_context"  # Historical context analysis
    YOUTUBE_PROCESSING = "youtube_processing"  # YouTube video summarization
    YOUTUBE_RSS_PROCESSING = "youtube_rss_processing"  # YouTube RSS feed processing
    CAPTION_PROOFREADING = "caption_proofreading"  # Caption/transcript proofreading
    ENTITY_EXTRACTION = "entity_extraction"  # Entity extraction for knowledge graph
    RERANKING = "reranking"  # Search result reranking (Graphiti)
    PODCAST_SCRIPT = "podcast_script"  # Podcast script generation from digest
    VOICE_CLEANUP = "voice_cleanup"  # Voice transcript cleanup/polishing
    IMAGE_SUGGESTION = "image_suggestion"  # LLM-based image content analysis
    CLOUD_STT = "cloud_stt"  # Cloud speech-to-text transcription
    CONTENT_FILTERING = "content_filtering"  # Content relevance classification


# Map of env var names per model step (e.g., MODEL_SUMMARIZATION)
_STEP_ENV_VARS: dict[str, str] = {step.value: f"MODEL_{step.value.upper()}" for step in ModelStep}


def _get_db_model_override(step: str) -> str | None:
    """Look up a model override from the settings_overrides table.

    Uses a lazy import to avoid circular dependencies between config and storage.
    Returns None if no override exists or if the DB is unavailable.
    """
    try:
        from src.services.settings_service import SettingsService
        from src.storage.database import get_db

        with get_db() as db:
            service = SettingsService(db)
            return service.get(f"model.{step}")
    except Exception:
        # DB not available (e.g., during startup, CLI without DB)
        logger.debug("DB model override lookup failed for %s", step)
        return None


@dataclass
class ProviderConfig:
    """Configuration for accessing a provider."""

    provider: Provider
    api_key: str
    # Provider-specific settings
    region: str | None = None  # For AWS Bedrock, Azure (e.g., "us-east-1")
    project_id: str | None = None  # For Google Vertex AI
    resource_name: str | None = None  # For Azure (deployment name)
    endpoint: str | None = None  # Custom endpoint URL
    # Rate limiting
    max_requests_per_minute: int = 60
    max_tokens_per_minute: int = 100_000


@dataclass
class ModelInfo:
    """Information about an LLM model (provider-agnostic)."""

    id: str  # Model identifier (family-based, e.g., "claude-sonnet-4-5")
    family: ModelFamily
    name: str  # Human-readable name
    # Capabilities (same across all providers)
    supports_vision: bool = False  # Whether model supports image inputs
    supports_video: bool = False  # Whether model supports video inputs (e.g., YouTube URLs)
    supports_audio: bool = False  # Whether model supports audio inputs (e.g., cloud STT)
    default_version: str | None = None  # Default version date (e.g., "20250929")


@dataclass
class ProviderModelConfig:
    """Provider-specific configuration for a model.

    Same model can have different costs, limits, and tiers on different providers.
    """

    model_id: str  # General model identifier (e.g., "claude-sonnet-4-5")
    provider: Provider  # Where to access it
    provider_model_id: str  # Provider-specific model identifier
    # Examples:
    # - Anthropic: "claude-sonnet-4-5-20250929"
    # - AWS Bedrock: "anthropic.claude-sonnet-4-5-20250929-v1:0"
    # - Vertex AI: "claude-sonnet-4-5@20250929"
    # Provider-specific pricing
    cost_per_mtok_input: float  # Cost per million input tokens (USD)
    cost_per_mtok_output: float  # Cost per million output tokens (USD)
    # Provider-specific limits
    context_window: int  # Maximum context window in tokens
    max_output_tokens: int  # Maximum output tokens
    # Provider tier (affects pricing/limits)
    tier: str = "standard"  # e.g., "standard", "enterprise", "on-demand", "provisioned"

    @property
    def version(self) -> str:
        """Extract version (YYYYMMDD) from provider_model_id.

        Returns:
            Version string (e.g., "20250929") or "unknown" if not found
        """
        import re

        match = re.search(r"(\d{8})", self.provider_model_id)
        return match.group(1) if match else "unknown"


def load_model_registry() -> tuple[
    dict[str, ModelInfo], dict[tuple[str, Provider], ProviderModelConfig], dict[str, str]
]:
    """Load model registry from YAML configuration file.

    Returns:
        Tuple of (model_registry, provider_model_configs, default_models)
    """
    # Load from ConfigRegistry if available, otherwise fallback to direct file read
    config = None
    try:
        from src.config.config_registry import get_config_registry

        registry = get_config_registry()
        if "models" in registry.registered_domains:
            config = registry.get_raw("models")
    except Exception:
        pass

    if config is None:
        # Fallback: direct YAML read (for tests or early startup)
        config_dir = Path(__file__).parent
        yaml_path = config_dir / "model_registry.yaml"
        settings_path = Path(__file__).resolve().parent.parent / "settings" / "models.yaml"

        actual_path = settings_path if settings_path.exists() else yaml_path

        if not actual_path.exists():
            raise FileNotFoundError(
                f"Model registry not found. Checked: {settings_path}, {yaml_path}"
            )

        with open(actual_path) as f:
            config = yaml.safe_load(f)

    # Parse models (now family-based IDs)
    model_registry = {}
    for model_id, model_data in config.get("models", {}).items():
        model_registry[model_id] = ModelInfo(
            id=model_id,  # Now: family-based like "claude-sonnet-4-5"
            family=ModelFamily(model_data["family"]),
            name=model_data["name"],
            supports_vision=model_data.get("supports_vision", False),
            supports_video=model_data.get("supports_video", False),
            supports_audio=model_data.get("supports_audio", False),
            default_version=model_data.get("default_version"),
        )

    # Parse provider-model configs (with provider-specific model IDs)
    provider_model_configs = {}
    for key, pmc_data in config.get("provider_model_configs", {}).items():
        # Parse key: "provider.model_id" (model_id is family-based)
        provider_str, model_id = key.split(".", 1)
        provider = Provider(provider_str)

        provider_model_configs[model_id, provider] = ProviderModelConfig(
            model_id=model_id,  # General ID (e.g., "claude-sonnet-4-5")
            provider=provider,
            provider_model_id=pmc_data["provider_model_id"],  # NEW: Provider-specific ID
            cost_per_mtok_input=pmc_data["cost_per_mtok_input"],
            cost_per_mtok_output=pmc_data["cost_per_mtok_output"],
            context_window=pmc_data["context_window"],
            max_output_tokens=pmc_data["max_output_tokens"],
            tier=pmc_data.get("tier", "standard"),
        )

    # Parse default models
    default_models = config.get("default_models", {})

    return model_registry, provider_model_configs, default_models


# Load registry on module import
MODEL_REGISTRY, PROVIDER_MODEL_CONFIGS, DEFAULT_MODELS = load_model_registry()


class ModelConfig:
    """Configuration for model selection and provider management."""

    def __init__(
        self,
        # Model selection per step (can override defaults)
        summarization: str | None = None,
        theme_analysis: str | None = None,
        digest_creation: str | None = None,
        digest_revision: str | None = None,
        historical_context: str | None = None,
        youtube_processing: str | None = None,
        youtube_rss_processing: str | None = None,
        caption_proofreading: str | None = None,
        entity_extraction: str | None = None,
        reranking: str | None = None,
        podcast_script: str | None = None,
        voice_cleanup: str | None = None,
        image_suggestion: str | None = None,
        cloud_stt: str | None = None,
        # Provider configurations (in priority order for failover)
        providers: list[ProviderConfig] | None = None,
    ):
        """Initialize model configuration.

        Args:
            summarization: Model for content summarization (default from YAML)
            theme_analysis: Model for theme analysis (default from YAML)
            digest_creation: Model for digest generation (default from YAML)
            digest_revision: Model for interactive digest revision (default from YAML)
            historical_context: Model for historical context (default from YAML)
            youtube_processing: Model for YouTube processing (default from YAML)
            youtube_rss_processing: Model for YouTube RSS feed processing (default from YAML)
            caption_proofreading: Model for caption/transcript proofreading (default from YAML)
            entity_extraction: Model for entity extraction (default from YAML)
            reranking: Model for search reranking (default from YAML)
            podcast_script: Model for podcast script generation (default from YAML)
            voice_cleanup: Model for voice transcript cleanup (default from YAML)
            image_suggestion: Model for image suggestion analysis (default from YAML)
            cloud_stt: Model for cloud speech-to-text (default from YAML)
            providers: List of provider configurations in priority order
        """
        # Use defaults from YAML if not specified
        self._models = {
            ModelStep.SUMMARIZATION: summarization or DEFAULT_MODELS["summarization"],
            ModelStep.THEME_ANALYSIS: theme_analysis or DEFAULT_MODELS["theme_analysis"],
            ModelStep.DIGEST_CREATION: digest_creation or DEFAULT_MODELS["digest_creation"],
            ModelStep.DIGEST_REVISION: digest_revision or DEFAULT_MODELS["digest_revision"],
            ModelStep.HISTORICAL_CONTEXT: historical_context
            or DEFAULT_MODELS["historical_context"],
            ModelStep.YOUTUBE_PROCESSING: youtube_processing
            or DEFAULT_MODELS["youtube_processing"],
            ModelStep.YOUTUBE_RSS_PROCESSING: youtube_rss_processing
            or DEFAULT_MODELS["youtube_rss_processing"],
            ModelStep.CAPTION_PROOFREADING: caption_proofreading
            or DEFAULT_MODELS["caption_proofreading"],
            ModelStep.ENTITY_EXTRACTION: entity_extraction or DEFAULT_MODELS["entity_extraction"],
            ModelStep.RERANKING: reranking or DEFAULT_MODELS["reranking"],
            ModelStep.PODCAST_SCRIPT: podcast_script
            or DEFAULT_MODELS.get("podcast_script", DEFAULT_MODELS["digest_creation"]),
            ModelStep.VOICE_CLEANUP: voice_cleanup
            or DEFAULT_MODELS.get("voice_cleanup", DEFAULT_MODELS["summarization"]),
            ModelStep.IMAGE_SUGGESTION: image_suggestion
            or DEFAULT_MODELS.get("image_suggestion", DEFAULT_MODELS["summarization"]),
            ModelStep.CLOUD_STT: cloud_stt
            or DEFAULT_MODELS.get("cloud_stt", DEFAULT_MODELS["youtube_processing"]),
        }

        # Validate all models exist
        for step, model_id in self._models.items():
            if model_id not in MODEL_REGISTRY:
                raise ValueError(
                    f"Unknown model '{model_id}' for step '{step}'. "
                    f"Available: {list(MODEL_REGISTRY.keys())}"
                )

        self._providers = providers or []

    def get_model_for_step(self, step: ModelStep) -> str:
        """Get the model ID for a pipeline step.

        Resolution order (highest precedence first):
        1. Environment variable (MODEL_SUMMARIZATION, etc.)
        2. Database override (settings_overrides table, key: model.<step>)
        3. Constructor value / YAML default

        Args:
            step: Pipeline step

        Returns:
            Model ID (e.g., "claude-haiku-4-5")
        """
        # 1. Check env var
        env_var = _STEP_ENV_VARS[step.value]
        env_value = os.environ.get(env_var)
        if env_value and env_value in MODEL_REGISTRY:
            return env_value

        # 2. Check DB override
        db_value = _get_db_model_override(step.value)
        if db_value and db_value in MODEL_REGISTRY:
            return db_value

        # 3. Fall back to constructor value (from YAML defaults)
        return self._models[step]

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Get provider-agnostic model information.

        Args:
            model_id: Model identifier

        Returns:
            ModelInfo with capabilities

        Raises:
            ValueError: If model not found in registry
        """
        if model_id not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model: {model_id}. Available: {list(MODEL_REGISTRY.keys())}")
        return MODEL_REGISTRY[model_id]

    def get_provider_model_config(self, model_id: str, provider: Provider) -> ProviderModelConfig:
        """Get provider-specific configuration for a model.

        Args:
            model_id: Model identifier
            provider: Provider

        Returns:
            ProviderModelConfig with provider-specific pricing and limits

        Raises:
            ValueError: If model not available on provider
        """
        key = (model_id, provider)
        if key not in PROVIDER_MODEL_CONFIGS:
            available = [
                f"{p.value}.{m}" for (m, p) in PROVIDER_MODEL_CONFIGS.keys() if m == model_id
            ]
            raise ValueError(
                f"Model '{model_id}' not available on provider '{provider.value}'. "
                f"Available for this model: {available}"
            )
        return PROVIDER_MODEL_CONFIGS[key]

    def get_providers_for_model(self, model_id: str) -> list[ProviderConfig]:
        """Get available providers for a model in priority order.

        Enables automatic failover: if rate limited on first provider,
        system can try the next provider.

        Args:
            model_id: Model identifier

        Returns:
            List of ProviderConfig in priority order

        Raises:
            ValueError: If no configured providers support the model
        """
        # Find which providers support this model
        available_providers = set()
        for (mid, prov), _ in PROVIDER_MODEL_CONFIGS.items():
            if mid == model_id:
                available_providers.add(prov)

        # Filter configured providers by availability
        result = [p for p in self._providers if p.provider in available_providers]

        if not result:
            raise ValueError(
                f"Model '{model_id}' not available on any configured providers. "
                f"Model available on: {sorted(p.value for p in available_providers)}. "
                f"Configured: {[p.provider.value for p in self._providers]}"
            )

        return result

    def get_provider_model_id(self, model_id: str, provider: Provider) -> str:
        """Get the provider-specific model identifier for API calls.

        Args:
            model_id: General model identifier (e.g., "claude-sonnet-4-5")
            provider: Provider to get ID for

        Returns:
            Provider-specific model ID for API calls
            Examples:
            - Anthropic: "claude-sonnet-4-5-20250929"
            - AWS Bedrock: "anthropic.claude-sonnet-4-5-20250929-v1:0"
            - Vertex AI: "claude-sonnet-4-5@20250929"

        Raises:
            ValueError: If model not available on provider
        """
        config = self.get_provider_model_config(model_id, provider)
        return config.provider_model_id

    def get_model_version(self, model_id: str, provider: Provider) -> str:
        """Get the version of a model for a specific provider.

        Args:
            model_id: General model identifier (e.g., "claude-sonnet-4-5")
            provider: Provider to get version for

        Returns:
            Version string (e.g., "20250929") or "unknown" if not found
        """
        config = self.get_provider_model_config(model_id, provider)
        return config.version

    def add_provider(self, provider_config: ProviderConfig, priority: int = -1) -> None:
        """Add or update a provider configuration.

        Args:
            provider_config: Provider configuration
            priority: Position in priority list (0 = highest, -1 = lowest/append)
        """
        # Remove existing config for this provider
        self._providers = [p for p in self._providers if p.provider != provider_config.provider]

        # Add at specified priority
        if priority == -1 or priority >= len(self._providers):
            self._providers.append(provider_config)
        else:
            self._providers.insert(priority, provider_config)

    def calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        provider: Provider | None = None,
    ) -> float:
        """Calculate cost for model usage.

        Args:
            model_id: Model identifier
            input_tokens: Input tokens
            output_tokens: Output tokens
            provider: Specific provider. If None, uses first available provider.

        Returns:
            Total cost in USD

        Raises:
            ValueError: If model or provider not available
        """
        # Use first available provider if not specified
        if provider is None:
            providers = self.get_providers_for_model(model_id)
            provider = providers[0].provider if providers else None

        if provider is None:
            raise ValueError(
                f"No providers configured for model '{model_id}'. "
                "Add providers with add_provider() or pass to constructor."
            )

        # Get provider-specific pricing
        config = self.get_provider_model_config(model_id, provider)

        input_cost = (input_tokens / 1_000_000) * config.cost_per_mtok_input
        output_cost = (output_tokens / 1_000_000) * config.cost_per_mtok_output

        return input_cost + output_cost

    def get_family(self, model_id: str) -> ModelFamily:
        """Get the model family.

        Args:
            model_id: Model identifier

        Returns:
            Model family (CLAUDE, GEMINI, or GPT)
        """
        return self.get_model_info(model_id).family

    def set_model_for_step(self, step: ModelStep, model_id: str) -> None:
        """Override the model for a specific step.

        Args:
            step: Pipeline step
            model_id: Model identifier

        Raises:
            ValueError: If model not found in registry
        """
        if model_id not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model: {model_id}. Available: {list(MODEL_REGISTRY.keys())}")
        self._models[step] = model_id

    def get_all_models(self) -> dict[ModelStep, str]:
        """Get all configured models.

        Returns:
            Dictionary mapping steps to model IDs
        """
        return self._models.copy()

    def get_available_models_for_provider(self, provider: Provider) -> list[str]:
        """Get all models available on a specific provider.

        Args:
            provider: Provider to check

        Returns:
            List of model IDs available on that provider
        """
        return sorted(
            set(model_id for (model_id, prov) in PROVIDER_MODEL_CONFIGS.keys() if prov == provider)
        )

    def get_cost_estimate(
        self,
        content_items_per_day: int = 10,
        digests_per_week: int = 2,
        youtube_videos_per_week: int = 5,
        provider: Provider | None = None,
    ) -> dict[str, float]:
        """Estimate monthly costs based on usage patterns.

        Args:
            content_items_per_day: Content items processed daily
            digests_per_week: Digests generated per week
            youtube_videos_per_week: YouTube videos per week
            provider: Provider for cost calculation. If None, uses first available.

        Returns:
            Cost breakdown by step and total

        Example:
            >>> config = get_model_config()
            >>> estimate = config.get_cost_estimate(
            ...     content_items_per_day=10,
            ...     digests_per_week=2
            ... )
            >>> print(f"Monthly cost: ${estimate['total']:.2f}")
        """
        # Token estimates per operation (rough averages)
        TOKEN_ESTIMATES = {
            "summarization": {"input": 8000, "output": 1500},
            "theme_analysis": {"input": 15000, "output": 3000},
            "digest_creation": {"input": 20000, "output": 4000},
            "historical_context": {"input": 10000, "output": 2000},
            "youtube": {"input": 12000, "output": 2000},
        }

        # Monthly operations
        monthly_content_items = content_items_per_day * 30
        monthly_digests = digests_per_week * 4
        monthly_youtube = youtube_videos_per_week * 4

        costs = {}

        # Summarization
        model = self.get_model_for_step(ModelStep.SUMMARIZATION)
        costs["summarization"] = self.calculate_cost(
            model,
            monthly_content_items * TOKEN_ESTIMATES["summarization"]["input"],
            monthly_content_items * TOKEN_ESTIMATES["summarization"]["output"],
            provider,
        )

        # Theme analysis
        model = self.get_model_for_step(ModelStep.THEME_ANALYSIS)
        costs["theme_analysis"] = self.calculate_cost(
            model,
            monthly_digests * TOKEN_ESTIMATES["theme_analysis"]["input"],
            monthly_digests * TOKEN_ESTIMATES["theme_analysis"]["output"],
            provider,
        )

        # Digest creation
        model = self.get_model_for_step(ModelStep.DIGEST_CREATION)
        costs["digest_creation"] = self.calculate_cost(
            model,
            monthly_digests * TOKEN_ESTIMATES["digest_creation"]["input"],
            monthly_digests * TOKEN_ESTIMATES["digest_creation"]["output"],
            provider,
        )

        # Historical context (assume 50% usage)
        model = self.get_model_for_step(ModelStep.HISTORICAL_CONTEXT)
        costs["historical_context"] = self.calculate_cost(
            model,
            int(monthly_digests * 0.5 * TOKEN_ESTIMATES["historical_context"]["input"]),
            int(monthly_digests * 0.5 * TOKEN_ESTIMATES["historical_context"]["output"]),
            provider,
        )

        # YouTube processing
        model = self.get_model_for_step(ModelStep.YOUTUBE_PROCESSING)
        costs["youtube_processing"] = self.calculate_cost(
            model,
            monthly_youtube * TOKEN_ESTIMATES["youtube"]["input"],
            monthly_youtube * TOKEN_ESTIMATES["youtube"]["output"],
            provider,
        )

        costs["total"] = sum(costs.values())

        return costs


# Global instance
_model_config: ModelConfig | None = None


def get_model_config() -> ModelConfig:
    """Get the global model configuration.

    Returns:
        ModelConfig instance with defaults from YAML

    Example:
        >>> from src.config.models import get_model_config, ModelStep
        >>> config = get_model_config()
        >>> model = config.get_model_for_step(ModelStep.SUMMARIZATION)
        >>> print(model)
        'claude-haiku-4-5-20251001'
    """
    global _model_config
    if _model_config is None:
        _model_config = ModelConfig()
    return _model_config


def set_model_config(config: ModelConfig) -> None:
    """Set the global model configuration.

    Args:
        config: ModelConfig instance
    """
    global _model_config
    _model_config = config
