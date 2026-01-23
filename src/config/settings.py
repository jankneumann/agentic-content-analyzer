"""Application configuration management."""

import logging
import warnings
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.models import ModelConfig, Provider, ProviderConfig

logger = logging.getLogger(__name__)

# Type alias for database provider
DatabaseProviderType = Literal["local", "supabase", "neon"]
PoolerModeType = Literal["transaction", "session"]


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
    database_url: str = (
        "postgresql://newsletter_user:newsletter_password@localhost:5432/newsletters"
    )
    redis_url: str = "redis://localhost:6379/0"

    # Database Provider Configuration
    # Explicit provider selection - no auto-detection magic
    database_provider: DatabaseProviderType = "local"

    # Supabase Cloud Database Configuration
    supabase_project_ref: str | None = None  # Supabase project reference ID
    supabase_db_password: str | None = None  # Supabase database password
    supabase_region: str = "us-east-1"  # AWS region for Supabase project
    supabase_pooler_mode: PoolerModeType = "transaction"  # Connection pooling mode
    supabase_direct_url: str | None = None  # Direct URL for migrations (bypasses pooler)
    supabase_az: str = (
        "0"  # AWS availability zone (0, 1, etc.) - check your Supabase connection string
    )

    # Neon Serverless PostgreSQL Configuration
    neon_api_key: str | None = None  # API key for branch management
    neon_project_id: str | None = None  # Project ID for branch management
    neon_default_branch: str = "main"  # Default parent branch for new branches
    neon_region: str | None = None  # Region (auto-detected from URL if not set)
    neon_direct_url: str | None = None  # Direct URL for migrations (bypasses pooler)

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

    # YouTube Configuration
    youtube_credentials_file: str = "youtube_credentials.json"
    youtube_token_file: str = "youtube_token.json"
    youtube_playlists_file: str = "youtube_playlists.txt"  # Config file for playlist IDs
    youtube_api_key: str | None = None  # For public playlists (falls back to google_api_key)

    # YouTube Keyframe Extraction (optional feature)
    youtube_keyframe_extraction: bool = False  # Enable/disable keyframe extraction
    youtube_temp_dir: str = (
        "/tmp/youtube_downloads"  # Temp storage for video downloads  # noqa: S108
    )
    youtube_scene_threshold: float = (
        0.3  # Scene detection sensitivity (0-1, lower = more sensitive)
    )
    youtube_similarity_threshold: float = 0.85  # Slide dedup threshold (0-1, higher = stricter)

    # Document Parser Configuration
    enable_docling: bool = True  # Enable Docling parser for advanced PDF/OCR
    docling_enable_ocr: bool = False  # Enable OCR for scanned documents (requires docling[ocr])
    docling_max_file_size_mb: int = 100  # Maximum file size for Docling processing
    docling_timeout_seconds: int = 300  # Processing timeout for large documents
    docling_cache_dir: str = "/tmp/docling"  # Cache directory for Docling models  # noqa: S108

    # File Upload Configuration
    max_upload_size_mb: int = 50  # Maximum file upload size

    # Image Storage Configuration
    image_storage_provider: str = "local"  # "local" or "s3"
    image_storage_path: str = "data/images"  # Local storage directory
    image_storage_bucket: str = "newsletter-images"  # S3 bucket name
    image_max_size_mb: int = 10  # Maximum image file size
    enable_image_extraction: bool = True  # Enable extraction from HTML/PDF
    enable_youtube_keyframes: bool = False  # Enable YouTube keyframe extraction

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

    @model_validator(mode="after")
    def validate_database_provider_config(self) -> "Settings":
        """Validate database provider configuration at startup.

        Ensures the configured provider matches the DATABASE_URL pattern
        and required provider-specific settings are present.

        Raises:
            ValueError: If provider configuration is invalid
        """
        match self.database_provider:
            case "neon":
                if ".neon.tech" not in self.database_url:
                    raise ValueError(
                        f"DATABASE_PROVIDER=neon requires DATABASE_URL containing .neon.tech. "
                        f"Got: {self._mask_url(self.database_url)}"
                    )
            case "supabase":
                has_supabase_config = self.supabase_project_ref or ".supabase." in self.database_url
                if not has_supabase_config:
                    raise ValueError(
                        "DATABASE_PROVIDER=supabase requires SUPABASE_PROJECT_REF "
                        "or DATABASE_URL containing .supabase."
                    )
            case "local":
                # Warn if URL looks like a cloud provider but local is selected
                if ".neon.tech" in self.database_url:
                    logger.warning(
                        "DATABASE_URL contains .neon.tech but DATABASE_PROVIDER=local. "
                        "Set DATABASE_PROVIDER=neon to use Neon features (branching, etc.)."
                    )
                elif ".supabase." in self.database_url:
                    logger.warning(
                        "DATABASE_URL contains .supabase. but DATABASE_PROVIDER=local. "
                        "Set DATABASE_PROVIDER=supabase to use Supabase features."
                    )
        return self

    def _mask_url(self, url: str) -> str:
        """Mask password in database URL for safe logging/errors.

        Args:
            url: Database URL potentially containing password

        Returns:
            URL with password replaced by ***
        """
        try:
            parsed = urlparse(url)
            if parsed.password:
                masked = url.replace(f":{parsed.password}@", ":***@")
                return masked
        except Exception:
            pass
        return url

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def detected_database_provider(self) -> DatabaseProviderType:
        """Return the configured database provider.

        .. deprecated::
            Use `settings.database_provider` directly instead.
            This property will be removed in a future version.

        Returns:
            The configured database provider ("local", "supabase", or "neon")
        """
        warnings.warn(
            "detected_database_provider is deprecated. " "Use settings.database_provider directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.database_provider

    def get_effective_database_url(self) -> str:
        """Get the effective database URL based on provider configuration.

        Returns the appropriate connection URL for the configured provider:
        - Local: Returns DATABASE_URL directly
        - Supabase: Constructs pooler URL from components, or uses DATABASE_URL
        - Neon: Returns DATABASE_URL (pooler conversion handled by NeonProvider)

        Returns:
            The database connection URL to use
        """
        match self.database_provider:
            case "supabase":
                return self._get_supabase_pooler_url()
            case "neon":
                # Neon provider handles pooler URL internally
                return self.database_url
            case _:  # "local" or any other value
                return self.database_url

    def _get_supabase_pooler_url(self) -> str:
        """Construct Supabase pooler URL from components or return DATABASE_URL."""
        if self.supabase_project_ref and self.supabase_db_password:
            port = 6543 if self.supabase_pooler_mode == "transaction" else 5432
            return (
                f"postgresql://postgres.{self.supabase_project_ref}:"
                f"{self.supabase_db_password}@"
                f"aws-{self.supabase_az}-{self.supabase_region}.pooler.supabase.com:"
                f"{port}/postgres"
            )
        return self.database_url

    def get_migration_database_url(self) -> str:
        """Get the database URL for Alembic migrations.

        Returns the direct (non-pooled) connection URL for the configured provider.
        DDL operations require direct connections, not pooled ones.

        Returns:
            Database URL suitable for migrations
        """
        match self.database_provider:
            case "supabase":
                return self._get_supabase_direct_url()
            case "neon":
                return self._get_neon_direct_url()
            case _:  # "local" or any other value
                return self.database_url

    def _get_supabase_direct_url(self) -> str:
        """Get Supabase direct URL for migrations (bypasses pooler)."""
        # Explicit direct URL takes precedence
        if self.supabase_direct_url:
            return self.supabase_direct_url

        # Construct from components
        if self.supabase_project_ref and self.supabase_db_password:
            return (
                f"postgresql://postgres:{self.supabase_db_password}@"
                f"db.{self.supabase_project_ref}.supabase.co:5432/postgres"
            )

        # Fall back to DATABASE_URL
        return self.database_url

    def _get_neon_direct_url(self) -> str:
        """Get Neon direct URL for migrations (bypasses pooler)."""
        # Explicit direct URL takes precedence
        if self.neon_direct_url:
            return self.neon_direct_url

        # Convert pooled URL to direct by removing -pooler suffix
        if "-pooler." in self.database_url:
            return self.database_url.replace("-pooler.", ".")

        # URL is already direct
        return self.database_url

    def get_youtube_api_key(self) -> str | None:
        """
        Get YouTube API key with fallback to Google API key.

        Returns:
            YOUTUBE_API_KEY if set, otherwise GOOGLE_API_KEY, or None if neither set
        """
        return self.youtube_api_key or self.google_api_key

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
            with open(self.rss_feeds_file) as f:
                file_feeds = [
                    line.strip() for line in f if line.strip() and not line.startswith("#")
                ]
                feeds.extend(file_feeds)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(feeds))

    def get_youtube_playlists(self) -> list[dict[str, str | None]]:
        """
        Get list of YouTube playlist configurations from config file.

        Reads from youtube_playlists.txt with format:
        PLAYLIST_ID | optional description
        Lines starting with # are comments

        Returns:
            List of dicts with 'id' and optional 'description'
        """
        import os

        playlists: list[dict[str, str | None]] = []

        if not os.path.exists(self.youtube_playlists_file):
            return playlists

        with open(self.youtube_playlists_file) as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse "PLAYLIST_ID | description" format
                if "|" in line:
                    playlist_id, description = line.split("|", 1)
                    playlists.append(
                        {
                            "id": playlist_id.strip(),
                            "description": description.strip(),
                        }
                    )
                else:
                    playlists.append(
                        {
                            "id": line.strip(),
                            "description": None,
                        }
                    )

        return playlists

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
    s = Settings()
    # Log provider configuration at startup
    logger.info(
        f"Database provider: {s.database_provider} | " f"URL: {s._mask_url(s.database_url)}"
    )
    return s


# Global settings instance
settings = get_settings()
