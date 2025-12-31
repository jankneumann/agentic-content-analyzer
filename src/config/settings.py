"""Application configuration management."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.models import ModelConfig, Provider, ProviderConfig


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql://newsletter_user:newsletter_password@localhost:5432/newsletters"
    redis_url: str = "redis://localhost:6379/0"

    # Neo4j / Graphiti
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "newsletter_password"
    semaphore_limit: int = 1  # Graphiti concurrency limit for LLM API calls

    # Agent Framework API Keys
    anthropic_api_key: str
    openai_api_key: str | None = None
    google_api_key: str | None = None

    # Gmail Configuration
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"

    # Substack RSS Configuration
    # Comma-separated list of RSS feed URLs
    rss_feeds: str = ""
    rss_feeds_file: str = "rss_feeds.txt"  # Optional file with one feed per line

    # Email Delivery
    sendgrid_api_key: str | None = None

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Digest Scheduling
    daily_digest_hour: int = 7  # 7am
    weekly_digest_day: int = 1  # Monday (0=Sunday, 1=Monday, etc.)
    weekly_digest_hour: int = 7  # 7am

    # Token Budget Configuration (for hierarchical digest creation)
    digest_context_window_percentage: float = 0.5  # Use 50% of context for input
    digest_newsletter_budget_percentage: float = 0.6  # 60% of input for newsletters
    digest_theme_budget_percentage: float = 0.3  # 30% of input for themes
    digest_prompt_overhead_percentage: float = 0.1  # 10% of input for prompt

    # Podcast / TTS Configuration
    podcast_voice_provider: str = "openai_tts"  # Default TTS provider
    podcast_output_format: str = "mp3"
    podcast_sample_rate: int = 44100
    podcast_words_per_minute: int = 150  # Average speaking rate
    podcast_storage_path: str = "data/podcasts"  # Local storage path

    # TTS Provider API Keys
    elevenlabs_api_key: str | None = None

    # Voice Persona Mappings (provider-specific voice IDs)
    # Configure in code via VOICE_PERSONA_CONFIG dict
    # ElevenLabs voice IDs - configure with actual voice IDs from your account
    elevenlabs_voice_alex_male: str = ""
    elevenlabs_voice_alex_female: str = ""
    elevenlabs_voice_sam_male: str = ""
    elevenlabs_voice_sam_female: str = ""

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    def get_rss_feed_urls(self) -> list[str]:
        """
        Get list of RSS feed URLs from config.

        Reads from RSS_FEEDS env var (comma-separated) or rss_feeds.txt file.

        Returns:
            List of RSS feed URLs
        """
        import os

        feeds = []

        # Try environment variable first
        if self.rss_feeds:
            feeds.extend([url.strip() for url in self.rss_feeds.split(",") if url.strip()])

        # Try feeds file if it exists
        if os.path.exists(self.rss_feeds_file):
            with open(self.rss_feeds_file, "r") as f:
                file_feeds = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                feeds.extend(file_feeds)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(feeds))

    def get_model_config(self) -> ModelConfig:
        """
        Get ModelConfig initialized with providers from environment.

        Configures providers in priority order:
        1. Anthropic (primary - direct API, lowest cost)
        2. AWS Bedrock (fallback - if configured)
        3. Google Vertex AI (fallback - if configured)
        4. Google AI (fallback - if configured)
        5. Microsoft Azure (fallback - if configured)
        6. OpenAI (primary for GPT models)

        Returns:
            ModelConfig instance with configured providers
        """
        config = ModelConfig()

        # Add Anthropic provider (primary for Claude models)
        if self.anthropic_api_key:
            config.add_provider(
                ProviderConfig(
                    provider=Provider.ANTHROPIC,
                    api_key=self.anthropic_api_key,
                )
            )

        # Add OpenAI provider (primary for GPT models)
        if self.openai_api_key:
            config.add_provider(
                ProviderConfig(
                    provider=Provider.OPENAI,
                    api_key=self.openai_api_key,
                )
            )

        # Add Google AI provider (primary for Gemini models)
        if self.google_api_key:
            config.add_provider(
                ProviderConfig(
                    provider=Provider.GOOGLE_AI,
                    api_key=self.google_api_key,
                )
            )

        # TODO: Add cloud provider fallbacks when configured
        # - AWS Bedrock (requires region, IAM credentials)
        # - Google Vertex AI (requires project_id, region, credentials)
        # - Microsoft Azure (requires endpoint, region, credentials)

        return config


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
