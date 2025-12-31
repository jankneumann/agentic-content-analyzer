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

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class Provider(str, Enum):
    """LLM provider/platform."""

    ANTHROPIC = "anthropic"  # Anthropic API (direct)
    AWS_BEDROCK = "aws_bedrock"  # AWS Bedrock
    GOOGLE_VERTEX = "google_vertex"  # Google Vertex AI
    MICROSOFT_AZURE = "microsoft_azure"  # Microsoft Azure OpenAI
    OPENAI = "openai"  # OpenAI API (direct)
    GOOGLE_AI = "google_ai"  # Google AI Studio (direct)


class ModelFamily(str, Enum):
    """Model family (across providers)."""

    CLAUDE = "claude"
    GEMINI = "gemini"
    GPT = "gpt"


class ModelStep(str, Enum):
    """Pipeline steps that use LLMs."""

    SUMMARIZATION = "summarization"  # Individual newsletter summarization
    THEME_ANALYSIS = "theme_analysis"  # Cross-newsletter theme extraction
    DIGEST_CREATION = "digest_creation"  # Digest generation
    DIGEST_REVISION = "digest_revision"  # Interactive digest revision
    HISTORICAL_CONTEXT = "historical_context"  # Historical context analysis
    YOUTUBE_PROCESSING = "youtube_processing"  # YouTube video summarization
    ENTITY_EXTRACTION = "entity_extraction"  # Entity extraction for knowledge graph
    RERANKING = "reranking"  # Search result reranking (Graphiti)
    PODCAST_SCRIPT = "podcast_script"  # Podcast script generation from digest


@dataclass
class ProviderConfig:
    """Configuration for accessing a provider."""

    provider: Provider
    api_key: str
    # Provider-specific settings
    region: Optional[str] = None  # For AWS Bedrock, Azure (e.g., "us-east-1")
    project_id: Optional[str] = None  # For Google Vertex AI
    resource_name: Optional[str] = None  # For Azure (deployment name)
    endpoint: Optional[str] = None  # Custom endpoint URL
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
    default_version: Optional[str] = None  # Default version date (e.g., "20250929")


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
        match = re.search(r'(\d{8})', self.provider_model_id)
        return match.group(1) if match else "unknown"


def load_model_registry() -> Tuple[
    Dict[str, ModelInfo], Dict[Tuple[str, Provider], ProviderModelConfig], Dict[str, str]
]:
    """Load model registry from YAML configuration file.

    Returns:
        Tuple of (model_registry, provider_model_configs, default_models)
    """
    # Find the YAML file
    config_dir = Path(__file__).parent
    yaml_path = config_dir / "model_registry.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Model registry not found: {yaml_path}. "
            "Ensure src/config/model_registry.yaml exists."
        )

    # Load YAML
    with open(yaml_path, "r") as f:
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
            default_version=model_data.get("default_version"),  # NEW
        )

    # Parse provider-model configs (with provider-specific model IDs)
    provider_model_configs = {}
    for key, pmc_data in config.get("provider_model_configs", {}).items():
        # Parse key: "provider.model_id" (model_id is family-based)
        provider_str, model_id = key.split(".", 1)
        provider = Provider(provider_str)

        provider_model_configs[(model_id, provider)] = ProviderModelConfig(
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
        summarization: Optional[str] = None,
        theme_analysis: Optional[str] = None,
        digest_creation: Optional[str] = None,
        digest_revision: Optional[str] = None,
        historical_context: Optional[str] = None,
        youtube_processing: Optional[str] = None,
        entity_extraction: Optional[str] = None,
        reranking: Optional[str] = None,
        podcast_script: Optional[str] = None,
        # Provider configurations (in priority order for failover)
        providers: Optional[List[ProviderConfig]] = None,
    ):
        """Initialize model configuration.

        Args:
            summarization: Model for newsletter summarization (default from YAML)
            theme_analysis: Model for theme analysis (default from YAML)
            digest_creation: Model for digest generation (default from YAML)
            digest_revision: Model for interactive digest revision (default from YAML)
            historical_context: Model for historical context (default from YAML)
            youtube_processing: Model for YouTube processing (default from YAML)
            entity_extraction: Model for entity extraction (default from YAML)
            reranking: Model for search reranking (default from YAML)
            podcast_script: Model for podcast script generation (default from YAML)
            providers: List of provider configurations in priority order
        """
        # Use defaults from YAML if not specified
        self._models = {
            ModelStep.SUMMARIZATION: summarization or DEFAULT_MODELS["summarization"],
            ModelStep.THEME_ANALYSIS: theme_analysis
            or DEFAULT_MODELS["theme_analysis"],
            ModelStep.DIGEST_CREATION: digest_creation
            or DEFAULT_MODELS["digest_creation"],
            ModelStep.DIGEST_REVISION: digest_revision
            or DEFAULT_MODELS["digest_revision"],
            ModelStep.HISTORICAL_CONTEXT: historical_context
            or DEFAULT_MODELS["historical_context"],
            ModelStep.YOUTUBE_PROCESSING: youtube_processing
            or DEFAULT_MODELS["youtube_processing"],
            ModelStep.ENTITY_EXTRACTION: entity_extraction
            or DEFAULT_MODELS["entity_extraction"],
            ModelStep.RERANKING: reranking or DEFAULT_MODELS["reranking"],
            ModelStep.PODCAST_SCRIPT: podcast_script
            or DEFAULT_MODELS.get("podcast_script", DEFAULT_MODELS["digest_creation"]),
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

        Args:
            step: Pipeline step

        Returns:
            Model ID (e.g., "claude-haiku-4-5-20251001")
        """
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
            raise ValueError(
                f"Unknown model: {model_id}. Available: {list(MODEL_REGISTRY.keys())}"
            )
        return MODEL_REGISTRY[model_id]

    def get_provider_model_config(
        self, model_id: str, provider: Provider
    ) -> ProviderModelConfig:
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
                f"{p.value}.{m}"
                for (m, p) in PROVIDER_MODEL_CONFIGS.keys()
                if m == model_id
            ]
            raise ValueError(
                f"Model '{model_id}' not available on provider '{provider.value}'. "
                f"Available for this model: {available}"
            )
        return PROVIDER_MODEL_CONFIGS[key]

    def get_providers_for_model(self, model_id: str) -> List[ProviderConfig]:
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
        self._providers = [
            p for p in self._providers if p.provider != provider_config.provider
        ]

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
        provider: Optional[Provider] = None,
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
            raise ValueError(
                f"Unknown model: {model_id}. Available: {list(MODEL_REGISTRY.keys())}"
            )
        self._models[step] = model_id

    def get_all_models(self) -> Dict[ModelStep, str]:
        """Get all configured models.

        Returns:
            Dictionary mapping steps to model IDs
        """
        return self._models.copy()

    def get_available_models_for_provider(self, provider: Provider) -> List[str]:
        """Get all models available on a specific provider.

        Args:
            provider: Provider to check

        Returns:
            List of model IDs available on that provider
        """
        return sorted(
            set(
                model_id
                for (model_id, prov) in PROVIDER_MODEL_CONFIGS.keys()
                if prov == provider
            )
        )

    def get_cost_estimate(
        self,
        newsletters_per_day: int = 10,
        digests_per_week: int = 2,
        youtube_videos_per_week: int = 5,
        provider: Optional[Provider] = None,
    ) -> Dict[str, float]:
        """Estimate monthly costs based on usage patterns.

        Args:
            newsletters_per_day: Newsletters processed daily
            digests_per_week: Digests generated per week
            youtube_videos_per_week: YouTube videos per week
            provider: Provider for cost calculation. If None, uses first available.

        Returns:
            Cost breakdown by step and total

        Example:
            >>> config = get_model_config()
            >>> estimate = config.get_cost_estimate(
            ...     newsletters_per_day=10,
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
        monthly_newsletters = newsletters_per_day * 30
        monthly_digests = digests_per_week * 4
        monthly_youtube = youtube_videos_per_week * 4

        costs = {}

        # Summarization
        model = self.get_model_for_step(ModelStep.SUMMARIZATION)
        costs["summarization"] = self.calculate_cost(
            model,
            monthly_newsletters * TOKEN_ESTIMATES["summarization"]["input"],
            monthly_newsletters * TOKEN_ESTIMATES["summarization"]["output"],
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
            int(
                monthly_digests * 0.5 * TOKEN_ESTIMATES["historical_context"]["output"]
            ),
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
_model_config: Optional[ModelConfig] = None


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
