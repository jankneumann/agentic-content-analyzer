"""Application configuration management."""

from __future__ import annotations

import logging
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

if TYPE_CHECKING:
    from src.config.sources import SourcesConfig

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.models import ModelConfig, Provider, ProviderConfig

logger = logging.getLogger(__name__)

# Type alias for database provider
DatabaseProviderType = Literal["local", "supabase", "neon", "railway"]
PoolerModeType = Literal["transaction", "session"]

# Type alias for Neo4j provider
Neo4jProviderType = Literal["local", "auradb"]

# Audio digest voice presets (maps friendly names to provider-specific voice IDs)
AUDIO_DIGEST_VOICE_PRESETS: dict[str, dict[str, str]] = {
    "professional": {"openai": "onyx", "elevenlabs": "nPczCjzI2devNBz1zQrb"},
    "warm": {"openai": "nova", "elevenlabs": "XrExE9yKIg1WjnnlVkGX"},
    "energetic": {"openai": "shimmer", "elevenlabs": "SAz9YHcvj6GT2YYXdXww"},
    "calm": {"openai": "alloy", "elevenlabs": "CwhRBWXzGAHq8TQ4Fs17"},
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (common in shared .env files)
    )

    # Environment
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # CORS Configuration
    # Comma-separated list of allowed origins, or "*" for all origins
    # Examples: "http://localhost:5173,http://localhost:3000" or "*"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    def get_allowed_origins_list(self) -> list[str]:
        """Parse allowed_origins string into a list.

        Returns:
            List of allowed origin URLs, or ["*"] for all origins
        """
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    # Database
    # DATABASE_URL is the primary connection URL (backward compatible)
    # Provider-specific URLs (LOCAL_DATABASE_URL, NEON_DATABASE_URL) take precedence when set
    database_url: str = (
        "postgresql://newsletter_user:newsletter_password@localhost:5432/newsletters"
    )
    local_database_url: str | None = None  # Override for local provider
    neon_database_url: str | None = None  # Override for neon provider
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

    # Local Supabase Development Configuration
    supabase_local: bool = False  # Enable local Supabase development mode
    # When True, auto-configures:
    #   - supabase_url -> http://127.0.0.1:54321
    #   - supabase_db_url -> postgresql://postgres:postgres@127.0.0.1:54322/postgres
    #   - supabase_anon_key / supabase_service_role_key -> local dev keys (from supabase status)
    supabase_url: str | None = None  # Supabase API URL (auto-configured for local)
    supabase_anon_key: str | None = None  # Supabase anon key (for local dev)

    # Default local Supabase keys (from supabase init - these are public test keys)
    # These are the default JWT tokens used by local Supabase for development
    _local_supabase_anon_key: str = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
        "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
    )
    _local_supabase_service_role_key: str = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
        "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
    )

    # Neon Serverless PostgreSQL Configuration
    neon_api_key: str | None = None  # API key for branch management
    neon_project_id: str | None = None  # Project ID for branch management
    neon_default_branch: str = "main"  # Default parent branch for new branches
    neon_region: str | None = None  # Region (auto-detected from URL if not set)
    neon_direct_url: str | None = None  # Direct URL for migrations (bypasses pooler)

    # Railway PostgreSQL Configuration
    # Railway provides PostgreSQL with automatic provisioning and SSL
    # When using custom image, extensions are available: pgvector, pg_search, pgmq, pg_cron
    railway_database_url: str | None = None  # Override for Railway provider

    # Railway extension support flags (enabled when using custom PostgreSQL image)
    railway_pg_cron_enabled: bool = True  # pg_cron for job scheduling
    railway_pgvector_enabled: bool = True  # pgvector for vector similarity
    railway_pg_search_enabled: bool = True  # pg_search (ParadeDB) for full-text search
    railway_pgmq_enabled: bool = True  # pgmq for message queue

    # Railway connection pool settings (defaults for Hobby plan: 512 MB RAM)
    railway_pool_size: int = 3  # Connections in pool (Hobby: 3, Pro: 10)
    railway_max_overflow: int = 2  # Additional connections (Hobby: 2, Pro: 10)
    railway_pool_recycle: int = 300  # Connection recycle interval (seconds)
    railway_pool_timeout: int = 30  # Connection timeout (seconds)

    # Railway MinIO Storage Configuration
    railway_minio_endpoint: str | None = None  # MinIO endpoint URL
    railway_minio_bucket: str | None = None  # MinIO bucket name
    minio_root_user: str | None = None  # MinIO root user (auto-injected by Railway)
    minio_root_password: str | None = None  # MinIO root password (auto-injected)

    # Neo4j / Graphiti Provider Configuration
    # Explicit provider selection - matches database provider pattern
    neo4j_provider: Neo4jProviderType = "local"

    # Legacy settings (for backward compatibility - used as fallbacks)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "newsletter_password"

    # Local Neo4j Configuration (Docker or local installation)
    neo4j_local_uri: str | None = None  # Override: bolt://localhost:7687
    neo4j_local_user: str | None = None  # Override: neo4j
    neo4j_local_password: str | None = None  # Override for local password

    # Neo4j AuraDB Configuration (cloud hosted)
    # Connection string format: neo4j+s://xxxxxxxx.databases.neo4j.io
    neo4j_auradb_uri: str | None = None  # Required for auradb provider
    neo4j_auradb_user: str = "neo4j"  # Usually "neo4j" for AuraDB
    neo4j_auradb_password: str | None = None  # Required for auradb provider

    # Graphiti concurrency limit for LLM API calls
    semaphore_limit: int = 1

    # Test Database Configuration (for integration tests)
    test_database_url: str | None = None
    test_neo4j_uri: str | None = None
    test_neo4j_user: str | None = None
    test_neo4j_password: str | None = None

    # Agent Framework API Keys
    anthropic_api_key: str
    openai_api_key: str | None = None
    google_api_key: str | None = None
    tavily_api_key: str | None = None
    admin_api_key: str | None = None  # Protects sensitive endpoints

    # Gmail Configuration
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"

    # Unified Source Configuration
    sources_config_dir: str = "sources.d"  # Directory with per-type YAML files
    sources_config_file: str = "sources.yaml"  # Single-file fallback

    # Substack RSS Configuration (legacy — use sources.d/ instead)
    # Comma-separated list of RSS feed URLs
    rss_feeds: str = ""
    rss_feeds_file: str = "rss_feeds.txt"  # Optional file with one feed per line

    # YouTube Configuration
    youtube_credentials_file: str = "youtube_credentials.json"
    youtube_token_file: str = "youtube_token.json"
    youtube_playlists_file: str = "youtube_playlists.txt"  # Legacy — use sources.d/ instead
    youtube_api_key: str | None = None  # For public playlists (falls back to google_api_key)

    # Podcast Ingestion Configuration
    podcast_stt_provider: str = "openai"  # STT provider: "openai" or "local_whisper"
    podcast_max_duration_minutes: int = 120  # Max episode duration to transcribe
    podcast_temp_dir: str = "/tmp/podcast_downloads"  # Temp dir for audio downloads  # noqa: S108

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
    image_storage_provider: str = "local"  # "local", "s3", or "supabase"
    image_storage_path: str = "data/images"  # Local storage directory
    image_storage_bucket: str = "newsletter-images"  # S3/Supabase bucket name
    image_max_size_mb: int = 10  # Maximum image file size
    enable_image_extraction: bool = True  # Enable extraction from HTML/PDF
    enable_youtube_keyframes: bool = False  # Enable YouTube keyframe extraction

    # S3 Storage Configuration (for image_storage_provider="s3")
    s3_endpoint_url: str | None = None  # Custom endpoint for S3-compatible services
    aws_region: str = "us-east-1"  # AWS region for S3
    aws_access_key_id: str | None = None  # AWS access key (uses boto3 defaults if not set)
    aws_secret_access_key: str | None = None  # AWS secret key (uses boto3 defaults if not set)

    # Supabase Storage Configuration (for image_storage_provider="supabase")
    # Requires supabase_project_ref from database config
    supabase_storage_bucket: str = "images"  # Supabase storage bucket name
    supabase_service_role_key: str | None = None  # Service role key (legacy, use access keys)
    supabase_access_key_id: str | None = None  # Supabase S3 access key ID
    supabase_secret_access_key: str | None = None  # Supabase S3 secret access key
    supabase_storage_public: bool = False  # Whether bucket is public (affects URL generation)
    # Note: supabase_local is defined in Local Supabase Development Configuration section above

    # Unified File Storage Configuration (supports multiple buckets)
    # Default provider for all buckets (can be overridden per-bucket)
    storage_provider: str = "local"  # "local", "s3", or "supabase"

    # Per-bucket provider overrides (JSON dict in env: STORAGE_BUCKET_PROVIDERS='{"podcasts": "s3"}')
    # If not specified, uses storage_provider (or image_storage_provider for backward compat)
    storage_bucket_providers: dict[str, str] | None = None

    # Local storage paths per bucket (defaults to data/{bucket})
    storage_local_paths: dict[str, str] | None = None

    # S3 bucket names per logical bucket (defaults to image_storage_bucket)
    storage_s3_buckets: dict[str, str] | None = None

    # Supabase bucket names per logical bucket (defaults to supabase_storage_bucket)
    storage_supabase_buckets: dict[str, str] | None = None

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

    # Audio Digest Configuration
    audio_digest_provider: str = "openai"  # TTS provider for digests
    audio_digest_default_voice: str = "nova"  # Default voice for narration
    audio_digest_speed: float = 1.0  # Playback speed (0.5 - 2.0)
    audio_digest_max_duration_minutes: int = 30  # Max digest length to convert

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
    def configure_local_supabase(self) -> Settings:
        """Auto-configure settings when local Supabase mode is enabled.

        When SUPABASE_LOCAL=true, automatically sets:
        - supabase_url -> http://127.0.0.1:54321
        - database_url -> postgresql://postgres:postgres@127.0.0.1:54322/postgres
        - supabase_anon_key / supabase_service_role_key -> local dev keys

        Also warns if mixing local flag with cloud URLs.
        """
        if not self.supabase_local:
            return self

        # Auto-configure local Supabase endpoints
        if self.supabase_url is None:
            object.__setattr__(self, "supabase_url", "http://127.0.0.1:54321")

        # Auto-configure local database URL if provider is supabase
        if self.database_provider == "supabase":
            local_db_url = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
            object.__setattr__(self, "database_url", local_db_url)
            # Set a placeholder project ref for local (validation requires it)
            if not self.supabase_project_ref:
                object.__setattr__(self, "supabase_project_ref", "local")
            # Set a placeholder password for local
            if not self.supabase_db_password:
                object.__setattr__(self, "supabase_db_password", "postgres")

        # Auto-configure local Supabase keys
        if self.supabase_anon_key is None:
            object.__setattr__(self, "supabase_anon_key", self._local_supabase_anon_key)
        if self.supabase_service_role_key is None:
            object.__setattr__(
                self, "supabase_service_role_key", self._local_supabase_service_role_key
            )

        # Warn if mixing local flag with cloud URLs
        if self.supabase_url and "supabase.co" in self.supabase_url:
            logger.warning(
                "SUPABASE_LOCAL=true but SUPABASE_URL contains 'supabase.co'. "
                "This may indicate mixing local and cloud configuration."
            )
        if self.database_url and "supabase.com" in self.database_url:
            logger.warning(
                "SUPABASE_LOCAL=true but DATABASE_URL contains 'supabase.com'. "
                "This may indicate mixing local and cloud configuration."
            )

        logger.info(
            f"Local Supabase mode enabled. API: {self.supabase_url}, "
            f"DB: postgresql://postgres:***@127.0.0.1:54322/postgres"
        )

        return self

    @model_validator(mode="after")
    def validate_database_provider_config(self) -> Settings:
        """Validate database provider configuration at startup.

        Ensures the configured provider has the required URL configured.
        Provider-specific URLs (NEON_DATABASE_URL, LOCAL_DATABASE_URL) take precedence
        over the generic DATABASE_URL when set.

        Raises:
            ValueError: If provider configuration is invalid
        """
        match self.database_provider:
            case "neon":
                # Check neon_database_url first, then database_url
                effective_url = self.neon_database_url or self.database_url
                if ".neon.tech" not in effective_url:
                    raise ValueError(
                        f"DATABASE_PROVIDER=neon requires a Neon URL containing .neon.tech. "
                        f"Set NEON_DATABASE_URL or DATABASE_URL appropriately. "
                        f"Got: {self._mask_url(effective_url)}"
                    )
            case "supabase":
                # Skip validation for local Supabase (project_ref is auto-set to "local")
                if not self.supabase_local and not self.supabase_project_ref:
                    raise ValueError(
                        "DATABASE_PROVIDER=supabase requires SUPABASE_PROJECT_REF to be set "
                        "(or set SUPABASE_LOCAL=true for local development)."
                    )
            case "railway":
                # Railway uses railway_database_url or database_url
                effective_url = self.railway_database_url or self.database_url
                if not effective_url:
                    raise ValueError(
                        "DATABASE_PROVIDER=railway requires DATABASE_URL or RAILWAY_DATABASE_URL "
                        "to be set."
                    )
            case "local":
                # Local provider uses local_database_url or database_url
                pass
        return self

    @model_validator(mode="after")
    def validate_neo4j_provider_config(self) -> Settings:
        """Validate Neo4j provider configuration at startup.

        Ensures the configured provider has the required credentials configured.
        Provider-specific settings take precedence over legacy settings.

        Raises:
            ValueError: If provider configuration is invalid
        """
        match self.neo4j_provider:
            case "auradb":
                if not self.neo4j_auradb_uri:
                    raise ValueError(
                        "NEO4J_PROVIDER=auradb requires NEO4J_AURADB_URI to be set. "
                        "Get this from your AuraDB console: neo4j+s://xxxxxxxx.databases.neo4j.io"
                    )
                if not self.neo4j_auradb_password:
                    raise ValueError(
                        "NEO4J_PROVIDER=auradb requires NEO4J_AURADB_PASSWORD to be set. "
                        "Get this from your AuraDB console when creating the instance."
                    )
            case "local":
                # Local provider uses local settings or legacy fallbacks
                pass
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
    def is_local_supabase(self) -> bool:
        """Check if using local Supabase development mode."""
        return self.supabase_local

    def get_supabase_storage_endpoint(self) -> str:
        """Get the Supabase Storage S3 endpoint URL.

        Returns:
            Local endpoint for local mode, cloud endpoint otherwise.
        """
        if self.supabase_local:
            return "http://127.0.0.1:54321/storage/v1/s3"
        if self.supabase_project_ref:
            return f"https://{self.supabase_project_ref}.supabase.co/storage/v1/s3"
        raise ValueError("Supabase project reference is required for storage.")

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

        Provider-specific URLs take precedence over database_url when set:
        - Local: LOCAL_DATABASE_URL > DATABASE_URL
        - Supabase: Constructs pooler URL from components, or uses DATABASE_URL
        - Neon: NEON_DATABASE_URL > DATABASE_URL
        - Railway: RAILWAY_DATABASE_URL > DATABASE_URL

        Returns:
            The database connection URL to use
        """
        match self.database_provider:
            case "supabase":
                return self._get_supabase_pooler_url()
            case "neon":
                return self.neon_database_url or self.database_url
            case "railway":
                return self.railway_database_url or self.database_url
            case _:  # "local" or any other value
                return self.local_database_url or self.database_url

    def _get_supabase_pooler_url(self) -> str:
        """Construct Supabase pooler URL from components."""
        # Local Supabase uses direct connection (no pooler)
        if self.supabase_local:
            return "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

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
                return self.local_database_url or self.database_url

    def _get_supabase_direct_url(self) -> str:
        """Get Supabase direct URL for migrations (bypasses pooler)."""
        # Local Supabase uses direct connection
        if self.supabase_local:
            return "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

        # Explicit direct URL takes precedence
        if self.supabase_direct_url:
            return self.supabase_direct_url

        # Construct from components
        if self.supabase_project_ref and self.supabase_db_password:
            return (
                f"postgresql://postgres:{self.supabase_db_password}@"
                f"db.{self.supabase_project_ref}.supabase.co:5432/postgres"
            )

        # Fall back to database_url
        return self.database_url

    def _get_neon_direct_url(self) -> str:
        """Get Neon direct URL for migrations (bypasses pooler)."""
        # Explicit direct URL takes precedence
        if self.neon_direct_url:
            return self.neon_direct_url

        neon_url = self.neon_database_url or self.database_url

        # Convert pooled URL to direct by removing -pooler suffix
        if "-pooler." in neon_url:
            return neon_url.replace("-pooler.", ".")

        # URL is already direct
        return neon_url

    def get_effective_neo4j_uri(self) -> str:
        """Get the effective Neo4j URI based on provider configuration.

        Provider-specific URIs take precedence over legacy settings:
        - Local: NEO4J_LOCAL_URI > NEO4J_URI > default
        - AuraDB: NEO4J_AURADB_URI (required)

        Returns:
            The Neo4j connection URI to use
        """
        match self.neo4j_provider:
            case "auradb":
                # AuraDB URI is required (validated in model_validator)
                return self.neo4j_auradb_uri or ""
            case _:  # "local"
                return self.neo4j_local_uri or self.neo4j_uri

    def get_effective_neo4j_user(self) -> str:
        """Get the effective Neo4j username based on provider configuration.

        Returns:
            The Neo4j username to use
        """
        match self.neo4j_provider:
            case "auradb":
                return self.neo4j_auradb_user
            case _:  # "local"
                return self.neo4j_local_user or self.neo4j_user

    def get_effective_neo4j_password(self) -> str:
        """Get the effective Neo4j password based on provider configuration.

        Returns:
            The Neo4j password to use
        """
        match self.neo4j_provider:
            case "auradb":
                # AuraDB password is required (validated in model_validator)
                return self.neo4j_auradb_password or ""
            case _:  # "local"
                return self.neo4j_local_password or self.neo4j_password

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

    def get_sources_config(self) -> SourcesConfig:
        """Get unified source configuration with three-tier resolution.

        Resolution order:
        1. sources.d/ directory (SOURCES_CONFIG_DIR) — recommended
        2. sources.yaml (SOURCES_CONFIG_FILE) — simpler setups
        3. Legacy files (rss_feeds.txt + youtube_playlists.txt) — fallback

        Returns:
            SourcesConfig with validated sources from the best available config
        """
        from src.config.sources import load_sources_config

        return load_sources_config(
            sources_dir=self.sources_config_dir,
            sources_file=self.sources_config_file,
            rss_feeds_file=self.rss_feeds_file,
            youtube_playlists_file=self.youtube_playlists_file,
        )

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

    def get_audio_digest_voice_id(self, preset: str | None = None) -> str:
        """Get the voice ID for audio digest generation.

        Args:
            preset: Optional preset name (professional, warm, energetic, calm)
                    Falls back to audio_digest_default_voice if not preset or unknown.

        Returns:
            Provider-specific voice ID
        """
        if preset and preset in AUDIO_DIGEST_VOICE_PRESETS:
            provider_voices = AUDIO_DIGEST_VOICE_PRESETS[preset]
            if self.audio_digest_provider in provider_voices:
                return provider_voices[self.audio_digest_provider]
        return self.audio_digest_default_voice


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    s = Settings()
    # Log provider configuration at startup
    logger.info(
        f"Database provider: {s.database_provider} | "
        f"URL: {s._mask_url(s.get_effective_database_url())}"
    )
    logger.info(f"Neo4j provider: {s.neo4j_provider} | " f"URI: {s.get_effective_neo4j_uri()}")
    return s


# Global settings instance
settings = get_settings()
