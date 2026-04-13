"""Application configuration management.

Settings can be loaded from:
1. Profile-based configuration (when PROFILE env var is set)
2. Traditional .env file (backward compatible default)

Profile loading order (highest to lowest priority):
1. Environment variables (always win)
2. Profile values (from profiles/{name}.yaml)
3. .env file values
4. Default values

See docs/PROFILES.md for profile configuration guide.
"""

from __future__ import annotations

import logging
import os
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from urllib.parse import urlparse

if TYPE_CHECKING:
    from src.config.sources import SourcesConfig

from pydantic import field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from src.config.models import ModelConfig, Provider, ProviderConfig

logger = logging.getLogger(__name__)

# Track the active profile name (set during Settings initialization)
_active_profile_name: str | None = None

# Common weak/default secrets that should not be used in production
_WEAK_SECRETS = {"changeme", "secret", "password", "admin", "test", "12345678"}


def _flatten_profile_to_settings(profile_data: dict[str, Any]) -> dict[str, Any]:
    """Flatten a profile dict into Settings-compatible flat dict.

    Converts nested profile structure to flat key-value pairs matching
    Settings field names (uppercase env-style names).

    Args:
        profile_data: Loaded and interpolated profile data

    Returns:
        Flat dict suitable for Settings model initialization
    """
    result: dict[str, Any] = {}

    # Flatten settings sections first
    settings = profile_data.get("settings", {})

    # Top-level settings (environment, log_level, etc.)
    for key in ["environment", "log_level", "allowed_origins", "auth_cookie_cross_origin"]:
        if key in settings:
            result[key] = settings[key]

    # Nested sections - flatten each one
    section_mappings = [
        "database",
        "neo4j",
        "graphdb",
        "storage",
        "observability",
        "api_keys",
        "digest",
        "search",
        "api",
    ]

    for section in section_mappings:
        section_data = settings.get(section, {})
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                if value is not None:
                    result[key] = value

    # Map providers to Settings provider fields AFTER settings flattening
    # so providers.* is authoritative over inherited settings like
    # settings.storage.storage_provider from base profiles
    providers = profile_data.get("providers", {})
    if "database" in providers:
        result["database_provider"] = providers["database"]
    if "graphdb" in providers:
        result["graphdb_provider"] = providers["graphdb"]
    if "neo4j" in providers:
        result["neo4j_provider"] = providers["neo4j"]
    if "storage" in providers:
        result["storage_provider"] = providers["storage"]
    if "observability" in providers:
        result["observability_provider"] = providers["observability"]

    return result


def _load_profile_settings() -> dict[str, Any] | None:
    """Load profile settings if PROFILE env var is set.

    Returns:
        Flattened profile settings dict, or None if no profile active
    """
    global _active_profile_name

    profile_name = os.environ.get("PROFILE")
    if not profile_name:
        return None

    try:
        # Import here to avoid circular imports
        from src.config.profiles import ProfileError, load_profile

        profile = load_profile(profile_name)
        _active_profile_name = profile_name

        # Convert Profile model to dict and flatten
        profile_dict = profile.model_dump()
        return _flatten_profile_to_settings(profile_dict)

    except ProfileError as e:
        logger.error(f"Failed to load profile '{profile_name}': {e}")
        raise


def get_active_profile_name() -> str | None:
    """Get the currently active profile name.

    Returns:
        Profile name if one is active, None otherwise
    """
    return _active_profile_name


def resolve_profile_settings(profile_name: str) -> Settings:
    """Resolve a named profile into a Settings instance without side effects.

    Loads the profile YAML, flattens it to Settings-compatible kwargs,
    and returns a standalone Settings instance. Does NOT mutate os.environ
    or the global _active_profile_name.

    Args:
        profile_name: Name of the profile to load (e.g. "local", "staging")

    Returns:
        A Settings instance configured from the named profile

    Raises:
        ProfileNotFoundError: If profile YAML does not exist (includes available profiles)
        ProfileResolutionError: If variable interpolation fails (re-raised with context)
    """
    from src.config.profiles import (
        ProfileNotFoundError,
        ProfileResolutionError,
        load_profile,
    )

    try:
        profile = load_profile(profile_name)
    except ProfileNotFoundError:
        raise
    except ProfileResolutionError as e:
        raise ProfileResolutionError(
            variable=e.variable,
            profile_name=e.profile_name,
            location=e.location,
        ) from e

    profile_dict = profile.model_dump()
    kwargs = _flatten_profile_to_settings(profile_dict)

    return Settings(_env_file=None, **kwargs)


# Type alias for database provider
DatabaseProviderType = Literal["local", "supabase", "neon", "railway"]
PoolerModeType = Literal["transaction", "session"]

# Type alias for Neo4j provider (deprecated — use GraphDBProviderType + GraphDBModeType)
Neo4jProviderType = Literal["local", "auradb"]

# Graph database provider and deployment mode (orthogonal axes)
GraphDBProviderType = Literal["neo4j", "falkordb"]
GraphDBModeType = Literal["local", "cloud", "embedded"]

# Type alias for observability provider
ObservabilityProviderType = Literal["noop", "opik", "braintrust", "otel", "langfuse"]

# Audio digest voice presets (maps friendly names to provider-specific voice IDs)
AUDIO_DIGEST_VOICE_PRESETS: dict[str, dict[str, str]] = {
    "professional": {"openai": "onyx", "elevenlabs": "nPczCjzI2devNBz1zQrb"},
    "warm": {"openai": "nova", "elevenlabs": "XrExE9yKIg1WjnnlVkGX"},
    "energetic": {"openai": "shimmer", "elevenlabs": "SAz9YHcvj6GT2YYXdXww"},
    "calm": {"openai": "alloy", "elevenlabs": "CwhRBWXzGAHq8TQ4Fs17"},
}


class ProfileSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from profile configuration.

    Loads values from profiles/{name}.yaml when PROFILE env var is set.
    Has lower priority than environment variables but higher than .env file.
    """

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._profile_settings: dict[str, Any] | None = None
        self._loaded = False

    def _load_once(self) -> dict[str, Any]:
        """Load profile settings once and cache."""
        if not self._loaded:
            self._profile_settings = _load_profile_settings()
            self._loaded = True
        return self._profile_settings or {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Get value for a specific field from profile settings.

        Returns:
            Tuple of (value, field_name, is_complex)
        """
        profile_data = self._load_once()
        value = profile_data.get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Return all settings from profile."""
        return self._load_once()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (common in shared .env files)
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include profile and OpenBao configuration.

        Priority order (highest to lowest):
        1. init_settings (values passed to Settings())
        2. env_settings (environment variables)
        3. bao_settings (OpenBao KV v2, when BAO_ADDR is configured)
        4. profile_settings (from profiles/{name}.yaml when PROFILE is set)
        5. dotenv_settings (.env file)
        6. file_secret_settings

        OpenBao is fully optional: when BAO_ADDR is not set or hvac is
        not installed, BaoSettingsSource returns empty and has zero overhead.
        """
        from src.config.bao_secrets import BaoSettingsSource

        profile_settings = ProfileSettingsSource(settings_cls)
        bao_settings = BaoSettingsSource(settings_cls)
        return (  # type: ignore[return-value]
            init_settings,
            env_settings,
            bao_settings,
            profile_settings,
            dotenv_settings,
            file_secret_settings,
        )

    # Environment
    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"

    # CORS Configuration
    # Comma-separated list of allowed origins, or "*" for all origins
    # Examples: "http://localhost:5173,http://localhost:3000" or "*"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000,capacitor://localhost,http://localhost,tauri://localhost"

    _DEV_DEFAULT_ORIGINS: ClassVar[set[str]] = {
        "http://localhost:5173",
        "http://localhost:3000",
        "capacitor://localhost",
        "http://localhost",
        "tauri://localhost",
    }

    def _is_dev_default_origins(self) -> bool:
        """Check if allowed_origins is still the development default value.

        Uses normalized set comparison so that ordering, spacing, or
        trailing commas don't bypass the production CORS deny.

        Returns:
            True if allowed_origins matches the dev default (localhost only)
        """
        origins = {o.strip() for o in self.allowed_origins.split(",") if o.strip()}
        return origins == self._DEV_DEFAULT_ORIGINS

    def get_allowed_origins_list(self) -> list[str]:
        """Parse allowed_origins string into a list.

        In production, if allowed_origins is still the development default
        (localhost only), returns an empty list to deny all cross-origin
        requests until explicit origins are configured.

        Returns:
            List of allowed origin URLs, or ["*"] for all origins,
            or [] in production with unconfigured origins
        """
        if self.environment == "production" and self._is_dev_default_origins():
            return []
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
    # Worker Configuration
    worker_enabled: bool = True  # Enable embedded queue worker in API process
    worker_concurrency: int = 5  # Max concurrent tasks (1-20)

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

    # Railway Backup Configuration (pg_cron → MinIO)
    railway_backup_enabled: bool = True  # Enable automated pg_dump backups
    railway_backup_schedule: str = "0 3 * * *"  # Cron schedule (default: daily 3 AM UTC)
    railway_backup_retention_days: int = 7  # Days to keep backups before cleanup
    railway_backup_bucket: str = "backups"  # MinIO bucket for backup storage
    railway_backup_staleness_hours: int = (
        48  # Hours before backup is considered stale (2x daily default)
    )

    # Railway MinIO Storage Configuration
    railway_minio_endpoint: str | None = None  # MinIO endpoint URL
    railway_minio_bucket: str | None = None  # MinIO bucket name
    minio_root_user: str | None = None  # MinIO root user (auto-injected by Railway)
    minio_root_password: str | None = None  # MinIO root password (auto-injected)

    # Graph Database Provider Configuration
    # Orthogonal axes: provider (what backend) x mode (how deployed)
    graphdb_provider: GraphDBProviderType = "neo4j"
    graphdb_mode: GraphDBModeType = "local"

    # Neo4j local connection (graphdb_provider=neo4j, graphdb_mode=local)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "newsletter_password"

    # Neo4j cloud connection (graphdb_provider=neo4j, graphdb_mode=cloud)
    neo4j_cloud_uri: str | None = None  # e.g. neo4j+s://xxx.databases.neo4j.io
    neo4j_cloud_user: str = "neo4j"
    neo4j_cloud_password: str | None = None

    # FalkorDB local connection (graphdb_provider=falkordb, graphdb_mode=local)
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    falkordb_database: str = "newsletter_graph"

    # FalkorDB cloud connection (graphdb_provider=falkordb, graphdb_mode=cloud)
    falkordb_cloud_host: str | None = None
    falkordb_cloud_port: int = 6379
    falkordb_cloud_password: str | None = None

    # FalkorDB embedded/Lite (graphdb_provider=falkordb, graphdb_mode=embedded)
    falkordb_lite_data_dir: str | None = None

    # Deprecated aliases (mapped to new fields in validator)
    neo4j_provider: Neo4jProviderType = "local"
    neo4j_local_uri: str | None = None
    neo4j_local_user: str | None = None
    neo4j_local_password: str | None = None
    neo4j_auradb_uri: str | None = None
    neo4j_auradb_user: str = "neo4j"
    neo4j_auradb_password: str | None = None

    # Graphiti concurrency limit for LLM API calls
    semaphore_limit: int = 1

    # Test Database Configuration (for integration tests)
    test_database_url: str | None = None
    test_neo4j_uri: str | None = None
    test_neo4j_user: str | None = None
    test_neo4j_password: str | None = None

    # Agent Framework API Keys
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    tavily_api_key: str | None = None
    admin_api_key: str | None = None  # Protects sensitive endpoints

    # Owner Authentication (Phase 1)
    app_secret_key: str | None = None  # Login password for browser/mobile access
    auth_cookie_cross_origin: bool = False  # SameSite=None for cross-origin deployments

    # Gmail Configuration
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"

    # Unified Source Configuration
    sources_config_dir: str = "sources.d"  # Directory with per-type YAML files
    sources_config_file: str = "sources.yaml"  # Single-file fallback

    # Substack Configuration
    substack_session_cookie: str | None = None  # Value of the substack.sid cookie

    # Substack RSS Configuration (legacy — use sources.d/ instead)
    # Comma-separated list of RSS feed URLs
    rss_feeds: str = ""
    rss_feeds_file: str = "rss_feeds.txt"  # Optional file with one feed per line

    # YouTube Configuration
    youtube_credentials_file: str = "youtube_credentials.json"
    youtube_token_file: str = "youtube_token.json"
    youtube_playlists_file: str = "youtube_playlists.txt"  # Legacy — use sources.d/ instead
    youtube_api_key: str | None = None  # For public playlists (falls back to google_api_key)
    youtube_max_retries: int = 4  # Maximum retry attempts for 429 errors
    youtube_backoff_base: float = 2.0  # Base delay in seconds for exponential backoff
    youtube_oauth_token_json: str | None = (
        None  # JSON string of OAuth token for headless cloud deployments
    )

    # Grok X Search Configuration
    xai_api_key: str | None = None  # xAI API key for Grok
    grok_model: str = "grok-4-1-fast"  # Model for X search (optimized for tool calling)
    grok_x_max_turns: int = 5  # Max tool calling turns per search
    grok_x_max_threads: int = 50  # Max threads per search run

    # Semantic Scholar Configuration
    semantic_scholar_api_key: str = ""  # Semantic Scholar API key (optional, increases rate limits)

    # Reference extraction and resolution
    reference_extraction_enabled: bool = True  # Extract refs on ingestion
    reference_auto_ingest_enabled: bool = False  # Auto-ingest unresolved refs (opt-in)
    reference_auto_ingest_max_depth: int = 1  # Max recursive auto-ingest depth
    reference_neo4j_sync_enabled: bool = True  # Sync resolved refs to Neo4j
    reference_min_confidence: float = 0.5  # Skip low-confidence URL-only refs below this threshold

    # Perplexity Search Configuration
    perplexity_api_key: str | None = None  # Perplexity API key
    perplexity_model: str = "sonar"  # sonar or sonar-pro
    perplexity_search_context_size: str = "medium"  # low, medium, high
    perplexity_search_recency_filter: str = "week"  # hour, day, week, month
    perplexity_max_results: int = 30  # Max articles per search run
    perplexity_domain_filter: list[str] = []  # Domain allow/deny list

    # Unified Web Search Provider (for ad-hoc search: chat, podcast, review)
    web_search_provider: str = "tavily"  # tavily, perplexity, grok

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

    # YouTube Async/Parallel Ingestion
    youtube_max_concurrent_videos: int = 5  # Max parallel videos per playlist
    youtube_max_concurrent_playlists: int = 3  # Max parallel playlists

    # Document Parser Configuration
    enable_docling: bool = True  # Enable Docling parser for advanced PDF/OCR
    docling_enable_ocr: bool = False  # Enable OCR for scanned documents (requires docling[ocr])
    docling_max_file_size_mb: int = 100  # Maximum file size for Docling processing
    docling_timeout_seconds: int = 300  # Processing timeout for large documents
    docling_cache_dir: str = "/tmp/docling"  # Cache directory for Docling models  # noqa: S108

    # Kreuzberg Parser Configuration
    enable_kreuzberg: bool = False  # Enable Kreuzberg parser (requires kreuzberg extra)
    kreuzberg_preferred_formats: str = ""  # Comma-separated formats to route to Kreuzberg
    kreuzberg_shadow_formats: str = ""  # Comma-separated formats for shadow comparison
    kreuzberg_max_file_size_mb: int = 100  # Maximum file size for Kreuzberg processing
    kreuzberg_timeout_seconds: int = 120  # Processing timeout (lower than Docling)

    # File Upload Configuration
    max_upload_size_mb: int = 50  # Maximum file upload size

    # Image Storage Configuration
    image_storage_provider: str = "local"  # "local", "s3", or "supabase"
    image_storage_path: str = "data/images"  # Local storage directory
    image_storage_bucket: str = "newsletter-images"  # S3/Supabase bucket name
    image_max_size_mb: int = 10  # Maximum image file size
    enable_image_extraction: bool = True  # Enable extraction from HTML/PDF
    enable_youtube_keyframes: bool = False  # Enable YouTube keyframe extraction

    # AI Image Generation
    image_generation_enabled: bool = False  # Feature flag for AI image generation
    image_generation_provider: str = "gemini"  # "gemini" (future: "openai", "stability")
    image_generation_model: str = "imagen-3.0-generate-001"  # Default image generation model
    image_generation_default_size: str = "1024x1024"  # Default dimensions
    image_generation_default_quality: str = "standard"  # "standard" or "hd"
    image_generation_default_style: str = "natural"  # Generation style guidance

    # Google Cloud / Vertex AI (for Gemini Imagen provider)
    google_cloud_project: str | None = None  # GCP project ID for Vertex AI
    google_cloud_location: str = "us-central1"  # GCP region

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

    # Observability Provider Configuration
    # Explicit provider selection — matches database/storage provider patterns
    observability_provider: ObservabilityProviderType = "noop"

    # OpenTelemetry (infrastructure layer — used by all providers except noop)
    otel_enabled: bool = False  # Enable OTel auto-instrumentation (FastAPI, SQLAlchemy, httpx)
    otel_service_name: str = "newsletter-aggregator"
    otel_exporter_otlp_endpoint: str | None = None  # OTLP HTTP endpoint URL
    otel_exporter_otlp_headers: str | None = None  # Comma-separated key=value headers
    otel_log_prompts: bool = False  # Log prompt/completion text (PII risk)
    otel_traces_sampler: str = "parentbased_traceidratio"
    otel_traces_sampler_arg: float = 1.0  # 1.0 = 100% in dev, lower in prod

    # OTel Log Bridge (requires otel_enabled=True)
    otel_logs_enabled: bool = True  # Enable log bridge to OTLP (gated by otel_enabled)
    otel_logs_export_level: str = (
        "WARNING"  # Min level for OTLP export (DEBUG, INFO, WARNING, ERROR)
    )
    log_format: Literal["text", "json"] = "json"  # Console output format

    # Opik Configuration (Comet Cloud or self-hosted)
    opik_api_key: str | None = None  # Comet Cloud API key
    opik_workspace: str | None = None  # Comet Cloud workspace
    opik_project_name: str = "newsletter-aggregator"  # Opik project name
    opik_base_url: str = "http://localhost:5174"  # Opik UI/nginx proxy URL
    opik_backend_url: str = "http://localhost:8080"  # Opik backend (health check)

    # Langfuse Configuration (Cloud or self-hosted)
    langfuse_public_key: str | None = None  # Langfuse public key (pk-lf-...)
    langfuse_secret_key: str | None = None  # Langfuse secret key (sk-lf-...)
    langfuse_base_url: str = "https://cloud.langfuse.com"  # Base URL (override for self-hosted)

    # Braintrust Configuration
    braintrust_api_key: str | None = None  # Braintrust API key
    braintrust_project_name: str = "newsletter-aggregator"  # Braintrust project name
    braintrust_api_url: str = "https://api.braintrust.dev"  # Braintrust API URL

    # Health Check Configuration
    health_check_timeout_seconds: int = 5  # Timeout for health check probes

    # Search & Embedding Configuration
    embedding_provider: str = "local"  # local, openai, voyage, cohere
    embedding_model: str = "all-MiniLM-L6-v2"  # Model name for chosen provider
    embedding_dimensions: int = 384  # Must match model output dimensions
    search_bm25_strategy: str = "auto"  # auto, paradedb, native
    search_rerank_enabled: bool = False
    search_rerank_provider: str = "cohere"  # cohere, jina, local, llm
    search_rerank_model: str | None = None  # None = provider default
    search_rerank_top_k: int = 50
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    search_bm25_weight: float = 0.5
    search_vector_weight: float = 0.5
    search_rrf_k: int = 60
    search_default_limit: int = 20
    search_max_limit: int = 100
    enable_search_indexing: bool = True

    # Chunk thinning — merge undersized chunks into adjacent ones
    min_node_tokens: int = 50  # 0 = disabled; range: 0-5000

    # Tree index chunking — hierarchical tree index for long structured documents
    tree_index_min_tokens: int = 8000  # Min content tokens for auto-selection; range: 1000-100000
    tree_index_min_heading_depth: int = 3  # Min heading depth (H1>H2>H3); range: 2-10
    tree_summarization_max_concurrent: int = 10  # Semaphore bound for LLM calls; range: 1-50
    tree_max_depth: int = 10  # Max tree nesting depth; range: 2-20

    # Tree search retrieval — LLM-based tree search for qualifying documents
    tree_search_enabled: bool = True
    tree_search_max_documents: int = 3  # Max docs for tree search per query; range: 1-20
    tree_search_timeout_seconds: int = 5  # Per-document timeout; range: 1-30
    tree_search_max_selected_nodes: int = 10  # Cap on LLM-selected nodes; range: 1-50
    search_tree_weight: float = 0.5  # RRF weight for tree search (alongside bm25/vector)

    # Local embedding model advanced settings
    embedding_trust_remote_code: bool = False  # Allow trust_remote_code for sentence-transformers
    embedding_max_seq_length: int | None = None  # Override model's max_seq_length

    # Search Provider API Keys
    voyage_api_key: str | None = None
    cohere_api_key: str | None = None
    jina_api_key: str | None = None

    # Crawl4AI Configuration
    # Fallback extractor for JavaScript-heavy pages (SPAs, dynamic content).
    # Requires crawl4ai optional dep or Docker server.
    crawl4ai_enabled: bool = False  # Feature flag — must explicitly enable
    crawl4ai_cache_mode: str = "bypass"  # bypass/enabled/disabled/read_only/write_only
    crawl4ai_server_url: str | None = None  # Remote server URL (e.g., http://localhost:11235)
    crawl4ai_page_timeout: int = 30000  # Page load timeout in ms
    crawl4ai_excluded_tags: list[str] = ["nav", "footer", "header"]  # HTML tags to exclude

    # CLI API Client Configuration
    # Used by CLI commands to target the backend API (local dev or cloud).
    # Override via profile settings.api.api_base_url or API_BASE_URL env var.
    api_base_url: str = "http://localhost:8000"
    api_timeout: int = 300  # seconds (5 min default for long-running ingestion)

    # Test / Hoverfly API Simulation Configuration
    # Set these to route HTTP clients through Hoverfly during integration tests.
    # When hoverfly_admin_url is set, test fixtures can upload simulations automatically.
    hoverfly_proxy_url: str = "http://localhost:8500"  # Hoverfly webserver URL
    hoverfly_admin_url: str = "http://localhost:8888"  # Hoverfly admin API URL

    # Knowledge Base Configuration
    # Topic compilation, health checks, and pipeline integration.
    kb_pipeline_enabled: bool = False  # Optional: run KB compile in `aca pipeline daily`
    kb_stale_threshold_days: int = 30  # Topics with no new evidence beyond this are stale
    kb_merge_similarity_threshold: float = 0.90  # Cosine similarity above this flags merge
    kb_match_similarity_threshold: float = 0.85  # Cosine similarity above this matches topics
    kb_min_topics_per_category: int = 3  # Minimum active topics per category (coverage gap)
    kb_compile_lock_timeout_minutes: int = 30  # Stale lock recovery threshold
    kb_qa_max_topics: int = 10  # Cap on relevant topics per Q&A query

    @model_validator(mode="after")
    def validate_search_config(self) -> Settings:
        """Validate search configuration cross-field constraints."""
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError(
                f"chunk_overlap_tokens ({self.chunk_overlap_tokens}) must be "
                f"less than chunk_size_tokens ({self.chunk_size_tokens})"
            )
        if not (0.0 <= self.search_bm25_weight <= 1.0):
            raise ValueError(
                f"search_bm25_weight must be between 0.0 and 1.0, got {self.search_bm25_weight}"
            )
        if not (0.0 <= self.search_vector_weight <= 1.0):
            raise ValueError(
                f"search_vector_weight must be between 0.0 and 1.0, got {self.search_vector_weight}"
            )

        # Warn if embedding_dimensions doesn't match known provider/model dims
        known_dims: dict[str, dict[str, int]] = {
            "openai": {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536,
            },
            "voyage": {"voyage-3": 1024, "voyage-3-lite": 512, "voyage-2": 1024},
            "cohere": {"embed-english-v3.0": 1024},
            "local": {
                "all-MiniLM-L6-v2": 384,
                "all-MiniLM-L12-v2": 384,
                "all-mpnet-base-v2": 768,
            },
        }
        provider_dims = known_dims.get(self.embedding_provider, {})
        expected = provider_dims.get(self.embedding_model)
        if expected is not None and self.embedding_dimensions != expected:
            logger.warning(
                f"EMBEDDING_DIMENSIONS={self.embedding_dimensions} does not match "
                f"known dimensions for {self.embedding_provider}/{self.embedding_model} "
                f"(expected {expected}). This may cause vector insertion errors."
            )

        return self

    @field_validator("otel_logs_export_level")
    @classmethod
    def validate_otel_logs_export_level(cls, v: str) -> str:
        """Validate that otel_logs_export_level is a known Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(
                f"OTEL_LOGS_EXPORT_LEVEL must be one of {sorted(valid_levels)}, got '{v}'"
            )
        return v.upper()

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
                # Warn if using default localhost URL — likely misconfigured for Railway
                if not self.railway_database_url and "localhost" in effective_url:
                    logger.warning(
                        "DATABASE_PROVIDER=railway but DATABASE_URL points to localhost. "
                        "Set RAILWAY_DATABASE_URL or update DATABASE_URL for Railway deployment."
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

    @model_validator(mode="after")
    def validate_observability_provider_config(self) -> Settings:
        """Validate observability provider configuration at startup.

        Ensures the configured provider has the required credentials.

        Raises:
            ValueError: If provider configuration is invalid
        """
        match self.observability_provider:
            case "braintrust":
                if not self.braintrust_api_key:
                    raise ValueError(
                        "OBSERVABILITY_PROVIDER=braintrust requires BRAINTRUST_API_KEY to be set. "
                        "Get this from https://www.braintrust.dev/app/settings"
                    )
            case "opik":
                # Opik works without API key for self-hosted; warn but don't error
                pass
            case "otel":
                if not self.otel_exporter_otlp_endpoint:
                    raise ValueError(
                        "OBSERVABILITY_PROVIDER=otel requires OTEL_EXPORTER_OTLP_ENDPOINT to be set."
                    )
            case "langfuse":
                has_public = bool(self.langfuse_public_key)
                has_secret = bool(self.langfuse_secret_key)
                if has_public != has_secret:
                    logger.warning(
                        "Langfuse provider has only one of public/secret key. "
                        "Both are required for authentication. Auth header will not be sent."
                    )
                elif not has_public and not has_secret:
                    logger.warning(
                        "Langfuse provider configured without API keys. "
                        "Traces will not be authenticated. "
                        "Get keys from Langfuse Settings → API Keys."
                    )
            case "noop":
                pass
        return self

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        """Warn about insecure configuration when running in production.

        Checks for common security misconfigurations:
        - Missing ADMIN_API_KEY (sensitive endpoints unprotected)
        - Default localhost-only CORS origins (likely misconfigured)

        Only emits warnings — does not raise errors.
        """
        if self.environment != "production":
            return self

        if not self.admin_api_key:
            logger.warning(
                "ADMIN_API_KEY is not set in production. "
                "Settings and prompt management endpoints will reject all requests."
            )

        if not self.app_secret_key and not self.admin_api_key:
            logger.warning(
                "Neither APP_SECRET_KEY nor ADMIN_API_KEY is set in production. "
                "All protected endpoints will be inaccessible."
            )
        elif not self.app_secret_key:
            logger.warning(
                "APP_SECRET_KEY is not set in production. "
                "Browser/mobile login will not be available. "
                "Only X-Admin-Key header authentication will work."
            )
        elif self.app_secret_key and len(self.app_secret_key) < 32:
            logger.warning(
                "APP_SECRET_KEY is shorter than 32 characters. "
                "Consider using a stronger key: aca manage generate-secret"
            )

        if self._is_dev_default_origins():
            logger.warning(
                "ALLOWED_ORIGINS is using development defaults (localhost only) in production. "
                "Cross-origin requests will be denied. "
                "Set ALLOWED_ORIGINS to your production frontend URL(s)."
            )

        # Check for weak APP_SECRET_KEY
        if self.app_secret_key and self.app_secret_key.lower() in _WEAK_SECRETS:
            logger.warning(
                "APP_SECRET_KEY matches a common default value. "
                "Use a strong random key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Check for weak ADMIN_API_KEY
        if self.admin_api_key and self.admin_api_key.lower() in _WEAK_SECRETS:
            logger.warning(
                "ADMIN_API_KEY matches a common default value. "
                "Use a strong random key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Check for short ADMIN_API_KEY
        if self.admin_api_key and len(self.admin_api_key) < 32:
            logger.warning(
                "ADMIN_API_KEY is shorter than 32 characters. "
                "Consider using a stronger key for production."
            )

        # Check for default database credentials
        if "newsletter_password" in self.database_url:
            logger.warning(
                "DATABASE_URL contains the default development password 'newsletter_password'. "
                "Use a strong random password for production databases."
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
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.environment == "staging"

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
            "detected_database_provider is deprecated. Use settings.database_provider directly.",
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
            case "railway":
                # Railway uses direct connections (no pooler), same URL for app and migrations
                return self.railway_database_url or self.database_url
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

    @model_validator(mode="after")
    def _validate_and_migrate_graphdb(self) -> Settings:
        """Wire up deprecated alias mapping and graphdb config validation.

        Runs after all fields are set. Order matters:
        1. Map deprecated neo4j_provider/neo4j_auradb_* → new fields
        2. Validate the resulting provider+mode combination
        """
        self._apply_deprecated_neo4j_aliases()
        self._validate_graphdb_config()
        return self

    def _apply_deprecated_neo4j_aliases(self) -> None:
        """Map deprecated neo4j_provider to graphdb_provider + graphdb_mode."""
        # Use model_fields_set to detect explicit assignment vs defaults
        explicitly_set = self.model_fields_set

        # Map neo4j_provider: auradb → graphdb_mode: cloud
        if "neo4j_provider" in explicitly_set and "graphdb_provider" not in explicitly_set:
            if self.neo4j_provider == "auradb":
                object.__setattr__(self, "graphdb_mode", "cloud")
                if self.neo4j_auradb_uri and not self.neo4j_cloud_uri:
                    object.__setattr__(self, "neo4j_cloud_uri", self.neo4j_auradb_uri)
                if self.neo4j_auradb_password and not self.neo4j_cloud_password:
                    object.__setattr__(self, "neo4j_cloud_password", self.neo4j_auradb_password)
                if self.neo4j_auradb_user != "neo4j":
                    object.__setattr__(self, "neo4j_cloud_user", self.neo4j_auradb_user)
                logger.warning(
                    "Deprecated: neo4j_provider='auradb' mapped to "
                    "graphdb_provider='neo4j', graphdb_mode='cloud'. "
                    "Update your config to use the new fields."
                )

        # Map deprecated neo4j_local_* → neo4j_* (always, if set)
        if self.neo4j_local_uri:
            object.__setattr__(self, "neo4j_uri", self.neo4j_local_uri)
            logger.warning("Deprecated: neo4j_local_uri mapped to neo4j_uri")
        if self.neo4j_local_user:
            object.__setattr__(self, "neo4j_user", self.neo4j_local_user)
        if self.neo4j_local_password:
            object.__setattr__(self, "neo4j_password", self.neo4j_local_password)

        # Map neo4j_auradb_* even when graphdb_provider is explicitly set
        if self.neo4j_auradb_uri and not self.neo4j_cloud_uri:
            object.__setattr__(self, "neo4j_cloud_uri", self.neo4j_auradb_uri)
        if self.neo4j_auradb_password and not self.neo4j_cloud_password:
            object.__setattr__(self, "neo4j_cloud_password", self.neo4j_auradb_password)

    def _validate_graphdb_config(self) -> None:
        """Validate graphdb_provider + graphdb_mode combination."""
        provider = self.graphdb_provider
        mode = self.graphdb_mode

        if provider == "neo4j" and mode == "embedded":
            raise ValueError(
                "Invalid configuration: graphdb_provider='neo4j' with graphdb_mode='embedded'. "
                "Neo4j does not support embedded mode. Use graphdb_provider='falkordb' for embedded."
            )

        if provider == "neo4j" and mode == "cloud":
            if not self.neo4j_cloud_uri:
                raise ValueError(
                    "Neo4j cloud mode requires NEO4J_CLOUD_URI "
                    "(e.g., neo4j+s://xxx.databases.neo4j.io)"
                )
            if not self.neo4j_cloud_password:
                raise ValueError("Neo4j cloud mode requires NEO4J_CLOUD_PASSWORD")

        if provider == "falkordb" and mode == "cloud":
            if not self.falkordb_cloud_host:
                raise ValueError("FalkorDB cloud mode requires FALKORDB_CLOUD_HOST")

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

    def _get_voice_db_override(self, field: str) -> str | None:
        """Look up a voice override from the settings_overrides table.

        Uses a lazy import to avoid circular dependencies.
        Returns None if no override exists or if the DB is unavailable.
        """
        try:
            from src.services.settings_service import SettingsService
            from src.storage.database import get_db

            with get_db() as db:
                service = SettingsService(db)
                return service.get(f"voice.{field}")
        except Exception:
            logger.debug("Voice DB override lookup failed for %s", field)
            return None

    def get_effective_voice_provider(self) -> str:
        """Get the effective TTS provider with DB override support.

        Resolution: env var > DB override > Settings default.
        """
        import os

        env_value = os.environ.get("AUDIO_DIGEST_PROVIDER")
        if env_value:
            return env_value
        db_value = self._get_voice_db_override("provider")
        if db_value:
            return db_value
        return self.audio_digest_provider

    def get_effective_voice(self) -> str:
        """Get the effective default voice with DB override support.

        Resolution: env var > DB override > Settings default.
        """
        import os

        env_value = os.environ.get("AUDIO_DIGEST_DEFAULT_VOICE")
        if env_value:
            return env_value
        db_value = self._get_voice_db_override("default_voice")
        if db_value:
            return db_value
        return self.audio_digest_default_voice

    def get_effective_voice_speed(self) -> float:
        """Get the effective voice speed with DB override support.

        Resolution: env var > DB override > Settings default.
        """
        import os

        env_value = os.environ.get("AUDIO_DIGEST_SPEED")
        if env_value:
            try:
                return float(env_value)
            except ValueError:
                pass
        db_value = self._get_voice_db_override("speed")
        if db_value:
            try:
                return float(db_value)
            except ValueError:
                pass
        return self.audio_digest_speed

    def get_audio_digest_voice_id(self, preset: str | None = None) -> str:
        """Get the voice ID for audio digest generation.

        Resolution order for voice:
        1. Preset lookup (if preset name provided and known)
        2. DB override (voice.default_voice in settings_overrides)
        3. Settings default (audio_digest_default_voice from env/config)

        Args:
            preset: Optional preset name (professional, warm, energetic, calm)
                    Falls back to effective default voice if not preset or unknown.

        Returns:
            Provider-specific voice ID
        """
        provider = self.get_effective_voice_provider()
        if preset and preset in AUDIO_DIGEST_VOICE_PRESETS:
            provider_voices = AUDIO_DIGEST_VOICE_PRESETS[preset]
            if provider in provider_voices:
                return provider_voices[provider]
        return self.get_effective_voice()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    s = Settings()

    # Log active profile if one is set
    profile_name = get_active_profile_name()
    if profile_name:
        logger.info(f"Active profile: {profile_name}")
    else:
        logger.info("No profile active (using .env configuration)")

    # Log provider configuration at startup
    logger.info(
        f"Database provider: {s.database_provider} | "
        f"URL: {s._mask_url(s.get_effective_database_url())}"
    )
    logger.info(f"Graph DB provider: {s.graphdb_provider} | mode: {s.graphdb_mode}")
    logger.info(f"Observability provider: {s.observability_provider}")
    return s


# Global settings instance
settings = get_settings()
