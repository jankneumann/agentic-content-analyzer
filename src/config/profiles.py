"""Profile-based configuration management.

This module provides YAML-based configuration profiles that separate
shareable settings from secrets. Profiles support:
- Named configurations for different environments (local, railway, supabase)
- Single-parent inheritance via `extends` field
- Environment variable interpolation via `${VAR}` syntax
- Provider-specific validation rules
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default profiles directory relative to project root
DEFAULT_PROFILES_DIR = "profiles"

# Type aliases matching existing Settings provider types
DatabaseProviderType = Literal["local", "supabase", "neon", "railway"]
Neo4jProviderType = Literal["local", "auradb"]
StorageProviderType = Literal["local", "s3", "supabase", "railway"]
ObservabilityProviderType = Literal["noop", "opik", "braintrust", "otel"]


# =============================================================================
# Exceptions
# =============================================================================


class ProfileError(Exception):
    """Base exception for profile-related errors."""

    pass


class ProfileNotFoundError(ProfileError):
    """Raised when a profile file cannot be found."""

    def __init__(self, profile_name: str, available: list[str] | None = None):
        self.profile_name = profile_name
        self.available = available or []
        msg = f"Profile '{profile_name}' not found"
        if self.available:
            msg += f". Available profiles: {', '.join(self.available)}"
        super().__init__(msg)


class ProfileParseError(ProfileError):
    """Raised when a profile file contains invalid YAML."""

    def __init__(self, profile_name: str, line: int | None = None, message: str = ""):
        self.profile_name = profile_name
        self.line = line
        msg = f"Failed to parse profile '{profile_name}'"
        if line:
            msg += f" at line {line}"
        if message:
            msg += f": {message}"
        super().__init__(msg)


class ProfileResolutionError(ProfileError):
    """Raised when environment variable interpolation fails."""

    def __init__(self, variable: str, profile_name: str, location: str = ""):
        self.variable = variable
        self.profile_name = profile_name
        self.location = location
        msg = f"Cannot resolve variable '${{{variable}}}' in profile '{profile_name}'"
        if location:
            msg += f" at {location}"
        super().__init__(msg)


class ProfileInheritanceCycleError(ProfileError):
    """Raised when profile inheritance forms a cycle."""

    def __init__(self, cycle_path: list[str]):
        self.cycle_path = cycle_path
        msg = f"Circular inheritance detected: {' -> '.join(cycle_path)}"
        super().__init__(msg)


class ProfileValidationError(ProfileError):
    """Raised when profile validation fails."""

    def __init__(self, profile_name: str, errors: list[str]):
        self.profile_name = profile_name
        self.errors = errors
        msg = f"Profile '{profile_name}' is invalid:\n"
        msg += "\n".join(f"  - {e}" for e in errors)
        super().__init__(msg)


class SecretsParseError(ProfileError):
    """Raised when secrets file contains invalid YAML."""

    def __init__(self, line: int | None = None, message: str = ""):
        self.line = line
        msg = "Failed to parse .secrets.yaml"
        if line:
            msg += f" at line {line}"
        if message:
            msg += f": {message}"
        super().__init__(msg)


# =============================================================================
# Provider Choices Model
# =============================================================================


class ProviderChoices(BaseModel):
    """Provider selections for each infrastructure category."""

    database: DatabaseProviderType = "local"
    neo4j: Neo4jProviderType = "local"
    storage: StorageProviderType = "local"
    observability: ObservabilityProviderType = "noop"


# =============================================================================
# Settings Models (Provider-specific configurations)
# =============================================================================


class DatabaseSettings(BaseModel):
    """Database-related settings grouped by provider.

    Settings are optional - only the ones relevant to the selected provider
    are required during validation.
    """

    # Common
    database_url: str | None = None

    # Local provider
    local_database_url: str | None = None

    # Supabase provider
    supabase_project_ref: str | None = None
    supabase_db_password: str | None = None
    supabase_region: str = "us-east-1"
    supabase_pooler_mode: Literal["transaction", "session"] = "transaction"
    supabase_direct_url: str | None = None
    supabase_az: str = "0"
    supabase_local: bool = False

    # Neon provider
    neon_database_url: str | None = None
    neon_api_key: str | None = None
    neon_project_id: str | None = None
    neon_direct_url: str | None = None

    # Railway provider
    railway_database_url: str | None = None
    railway_pool_size: int = 3
    railway_max_overflow: int = 2
    railway_pool_recycle: int = 300
    railway_pool_timeout: int = 30

    model_config = {"extra": "allow"}  # Allow additional settings


class Neo4jSettings(BaseModel):
    """Neo4j-related settings grouped by provider."""

    # Legacy/common settings
    neo4j_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None

    # Local provider
    neo4j_local_uri: str | None = None
    neo4j_local_user: str | None = None
    neo4j_local_password: str | None = None

    # AuraDB provider
    neo4j_auradb_uri: str | None = None
    neo4j_auradb_user: str = "neo4j"
    neo4j_auradb_password: str | None = None

    # Graphiti concurrency
    semaphore_limit: int = 1

    model_config = {"extra": "allow"}


class StorageSettings(BaseModel):
    """Storage-related settings grouped by provider."""

    # Common
    storage_provider: str = "local"
    image_storage_provider: str = "local"
    image_storage_path: str = "data/images"
    image_storage_bucket: str = "newsletter-images"
    image_max_size_mb: int = 10

    # S3 provider
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_endpoint_url: str | None = None

    # Supabase storage
    supabase_storage_bucket: str = "images"
    supabase_access_key_id: str | None = None
    supabase_secret_access_key: str | None = None
    supabase_storage_public: bool = False

    # Railway MinIO
    railway_minio_endpoint: str | None = None
    railway_minio_bucket: str | None = None
    minio_root_user: str | None = None
    minio_root_password: str | None = None

    model_config = {"extra": "allow"}


class ObservabilitySettings(BaseModel):
    """Observability-related settings grouped by provider."""

    # OpenTelemetry infrastructure
    otel_enabled: bool = False
    otel_service_name: str = "newsletter-aggregator"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None
    otel_log_prompts: bool = False
    otel_traces_sampler: str = "parentbased_traceidratio"
    otel_traces_sampler_arg: float = 1.0
    otel_logs_enabled: bool = True
    otel_logs_export_level: str = "WARNING"

    # Opik provider
    opik_api_key: str | None = None
    opik_workspace: str | None = None
    opik_project_name: str = "newsletter-aggregator"

    # Braintrust provider
    braintrust_api_key: str | None = None
    braintrust_project_name: str = "newsletter-aggregator"
    braintrust_api_url: str = "https://api.braintrust.dev"

    model_config = {"extra": "allow"}


class APIKeySettings(BaseModel):
    """API keys for various services."""

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    tavily_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    sendgrid_api_key: str | None = None
    admin_api_key: str | None = None

    model_config = {"extra": "allow"}


class DigestSettings(BaseModel):
    """Digest generation settings."""

    digest_context_window_percentage: float = 0.5
    digest_newsletter_budget_percentage: float = 0.6
    digest_theme_budget_percentage: float = 0.3
    digest_prompt_overhead_percentage: float = 0.1
    daily_digest_hour: int = 7
    weekly_digest_day: int = 1
    weekly_digest_hour: int = 7

    model_config = {"extra": "allow"}


class ProfileSettings(BaseModel):
    """Container for all profile settings sections."""

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    api_keys: APIKeySettings = Field(default_factory=APIKeySettings)
    digest: DigestSettings = Field(default_factory=DigestSettings)

    # Allow additional top-level settings
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = {"extra": "allow"}


# =============================================================================
# Profile Model
# =============================================================================


class Profile(BaseModel):
    """A configuration profile that can extend other profiles."""

    name: str
    extends: str | None = None
    description: str | None = None
    providers: ProviderChoices = Field(default_factory=ProviderChoices)
    settings: ProfileSettings = Field(default_factory=ProfileSettings)

    # Internal: track which profile values came from (for debugging)
    _sources: dict[str, str] = {}

    model_config = {"extra": "forbid"}


# =============================================================================
# Environment Variable Interpolation
# =============================================================================

# Regex patterns for interpolation
# ${VAR} - required variable
# ${VAR:-default} - variable with default
# $${VAR} - escaped (produces literal ${VAR})
INTERPOLATION_PATTERN = re.compile(
    r"""
    \$\$\{([^}]+)\}      |  # Escaped: $${VAR} -> ${VAR}
    \$\{([^}:]+):-([^}]*)\} |  # With default: ${VAR:-default}
    \$\{([^}]+)\}           # Required: ${VAR}
    """,
    re.VERBOSE,
)


def interpolate_value(
    value: str,
    env_vars: dict[str, str],
    secrets: dict[str, str],
    profile_name: str,
    path: str = "",
) -> str:
    """Interpolate environment variables in a string value.

    Resolution order (highest to lowest priority):
    1. Environment variables
    2. Secrets from .secrets.yaml
    3. Default value (if specified with ${VAR:-default})

    Args:
        value: String potentially containing ${VAR} references
        env_vars: Environment variables dict
        secrets: Secrets dict from .secrets.yaml
        profile_name: Name of profile (for error messages)
        path: Path to value in profile (for error messages)

    Returns:
        String with variables resolved

    Raises:
        ProfileResolutionError: If required variable is not found
    """

    def replacer(match: re.Match[str]) -> str:
        escaped, var_with_default, default, required_var = match.groups()

        # Escaped: $${VAR} -> ${VAR}
        if escaped:
            return f"${{{escaped}}}"

        # With default: ${VAR:-default}
        if var_with_default:
            # Check env first, then secrets, then use default
            if var_with_default in env_vars:
                return env_vars[var_with_default]
            if var_with_default in secrets:
                return secrets[var_with_default]
            return default

        # Required: ${VAR}
        if required_var:
            if required_var in env_vars:
                return env_vars[required_var]
            if required_var in secrets:
                return secrets[required_var]
            raise ProfileResolutionError(required_var, profile_name, path)

        return match.group(0)

    return INTERPOLATION_PATTERN.sub(replacer, value)


def interpolate_dict(
    data: dict[str, Any],
    env_vars: dict[str, str],
    secrets: dict[str, str],
    profile_name: str,
    path: str = "",
) -> dict[str, Any]:
    """Recursively interpolate all string values in a dictionary.

    Args:
        data: Dictionary with potentially unresolved variables
        env_vars: Environment variables dict
        secrets: Secrets dict from .secrets.yaml
        profile_name: Name of profile (for error messages)
        path: Current path in nested structure (for error messages)

    Returns:
        Dictionary with all variables resolved
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if isinstance(value, str):
            result[key] = interpolate_value(value, env_vars, secrets, profile_name, current_path)
        elif isinstance(value, dict):
            result[key] = interpolate_dict(value, env_vars, secrets, profile_name, current_path)
        elif isinstance(value, list):
            result[key] = [
                (
                    interpolate_value(item, env_vars, secrets, profile_name, f"{current_path}[{i}]")
                    if isinstance(item, str)
                    else (
                        interpolate_dict(
                            item, env_vars, secrets, profile_name, f"{current_path}[{i}]"
                        )
                        if isinstance(item, dict)
                        else item
                    )
                )
                for i, item in enumerate(value)
            ]
        else:
            result[key] = value

    return result


# =============================================================================
# Profile Loading and Inheritance
# =============================================================================


def get_profiles_dir() -> Path:
    """Get the profiles directory path.

    Returns the directory from PROFILES_DIR env var, or defaults to
    'profiles/' in the project root.
    """
    profiles_dir = os.environ.get("PROFILES_DIR", DEFAULT_PROFILES_DIR)
    return Path(profiles_dir)


def list_available_profiles(profiles_dir: Path | None = None) -> list[str]:
    """List all available profile names.

    Args:
        profiles_dir: Optional override for profiles directory

    Returns:
        List of profile names (without .yaml extension)
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()
    if not profiles_dir.exists():
        return []

    return sorted(
        p.stem for p in profiles_dir.glob("*.yaml") if p.is_file() and not p.stem.startswith("_")
    )


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Rules:
    - Scalar values: override wins
    - Dicts: recursively merge
    - Lists: override replaces base entirely

    Args:
        base: Base dictionary
        override: Dictionary with overriding values

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_profile_raw(name: str, profiles_dir: Path | None = None) -> dict[str, Any]:
    """Load raw profile data from YAML file without processing.

    Args:
        name: Profile name (without .yaml extension)
        profiles_dir: Optional override for profiles directory

    Returns:
        Raw dictionary from YAML file

    Raises:
        ProfileNotFoundError: If profile file doesn't exist
        ProfileParseError: If YAML is invalid
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()

    profile_path = profiles_dir / f"{name}.yaml"

    if not profiles_dir.exists():
        raise ProfileNotFoundError(name, [])

    if not profile_path.exists():
        available = list_available_profiles(profiles_dir)
        raise ProfileNotFoundError(name, available)

    try:
        with open(profile_path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
            return data
    except yaml.YAMLError as e:
        line = None
        if hasattr(e, "problem_mark") and e.problem_mark:
            line = e.problem_mark.line + 1
        raise ProfileParseError(name, line, str(e)) from e


def resolve_inheritance(
    name: str,
    profiles_dir: Path | None = None,
    _visited: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve profile inheritance and return merged data.

    Args:
        name: Profile name to load
        profiles_dir: Optional override for profiles directory
        _visited: Internal - tracks visited profiles for cycle detection

    Returns:
        Merged profile data with inheritance resolved

    Raises:
        ProfileInheritanceCycleError: If circular inheritance detected
        ProfileNotFoundError: If profile or parent not found
    """
    if _visited is None:
        _visited = []

    # Check for cycles
    if name in _visited:
        _visited.append(name)
        raise ProfileInheritanceCycleError(_visited)

    _visited.append(name)

    # Load this profile
    data = load_profile_raw(name, profiles_dir)

    # If no parent, return as-is
    if not data.get("extends"):
        return data

    # Load and merge parent
    parent_name = data["extends"]
    try:
        parent_data = resolve_inheritance(parent_name, profiles_dir, _visited.copy())
    except ProfileNotFoundError as e:
        # Re-raise with context about which profile referenced the missing parent
        raise ProfileNotFoundError(parent_name, [*e.available, f"(referenced by '{name}')"]) from e

    # Deep merge: parent is base, current profile overrides
    merged = deep_merge(parent_data, data)

    # Preserve the original profile's name, not the parent's
    merged["name"] = name

    return merged


def load_profile(
    name: str,
    secrets: dict[str, str] | None = None,
    env_vars: dict[str, str] | None = None,
    profiles_dir: Path | None = None,
    skip_interpolation: bool = False,
) -> Profile:
    """Load a profile with inheritance resolved and variables interpolated.

    Args:
        name: Profile name to load
        secrets: Secrets dict (defaults to loading from .secrets.yaml)
        env_vars: Environment variables (defaults to os.environ)
        profiles_dir: Optional override for profiles directory
        skip_interpolation: If True, skip variable interpolation (for validation)

    Returns:
        Fully resolved Profile object

    Raises:
        ProfileNotFoundError: If profile not found
        ProfileParseError: If YAML is invalid
        ProfileInheritanceCycleError: If circular inheritance
        ProfileResolutionError: If variable interpolation fails
    """
    # Resolve inheritance first
    data = resolve_inheritance(name, profiles_dir)

    # Ensure name is set
    if "name" not in data:
        data["name"] = name

    # Skip interpolation if requested (useful for structural validation)
    if skip_interpolation:
        return Profile.model_validate(data)

    # Load secrets and env vars
    if secrets is None:
        from src.config.secrets import load_secrets

        secrets = load_secrets()
    if env_vars is None:
        env_vars = dict(os.environ)

    # Interpolate variables
    interpolated = interpolate_dict(data, env_vars, secrets, name)

    return Profile.model_validate(interpolated)


def determine_active_profile() -> str | None:
    """Determine which profile should be active based on environment.

    Resolution order:
    1. PROFILE environment variable
    2. profiles/default.yaml exists
    3. None (fall back to .env)

    Returns:
        Profile name to use, or None if .env should be used
    """
    # Check PROFILE env var
    profile_env = os.environ.get("PROFILE")
    if profile_env:
        return profile_env

    # Check for default.yaml
    profiles_dir = get_profiles_dir()
    default_path = profiles_dir / "default.yaml"
    if default_path.exists():
        return "default"

    # Fall back to None (use .env)
    return None


# =============================================================================
# Profile Validation
# =============================================================================

# Required settings per provider
PROVIDER_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "database": {
        "local": [],  # Uses defaults
        "supabase": ["supabase_project_ref", "supabase_db_password"],
        "neon": ["neon_database_url"],
        "railway": ["railway_database_url"],
    },
    "neo4j": {
        "local": [],  # Uses defaults
        "auradb": ["neo4j_auradb_uri", "neo4j_auradb_password"],
    },
    "storage": {
        "local": [],  # Uses defaults
        "s3": ["image_storage_bucket", "aws_region"],
        "supabase": ["supabase_storage_bucket"],
        "railway": [],  # Uses Railway-injected vars
    },
    "observability": {
        "noop": [],
        "opik": [],  # Works without key for self-hosted
        "braintrust": ["braintrust_api_key"],
        "otel": ["otel_exporter_otlp_endpoint"],
    },
}

# Coherence rules: provider combinations that require each other
COHERENCE_RULES: list[tuple[str, str, str, str, list[str]]] = [
    # (provider_category, provider_value, requires_category, requires_value, or_settings)
    # storage: supabase requires database config for Supabase
    ("storage", "supabase", "database", "supabase", ["supabase_project_ref"]),
    # Note: storage: railway (MinIO) is independent of database provider —
    # Railway MinIO only needs minio_root_user/password, not railway_database_url.
    # No coherence rule needed for railway storage.
]


def get_setting_value(settings: ProfileSettings, category: str, key: str) -> Any:
    """Get a setting value from the appropriate category."""
    category_settings = getattr(settings, category, None)
    if category_settings is None:
        return None

    # Try direct attribute
    if hasattr(category_settings, key):
        return getattr(category_settings, key)

    # Try extra fields
    if hasattr(category_settings, "model_extra"):
        return category_settings.model_extra.get(key)

    return None


def validate_profile(
    profile: Profile,
    secrets: dict[str, str] | None = None,
    check_secrets: bool = True,
) -> list[str]:
    """Validate a profile for completeness and coherence.

    Args:
        profile: Profile to validate
        secrets: Available secrets (for checking unresolved references)
        check_secrets: If True, validate that secrets are available

    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []

    # Detect local Supabase mode — cloud-only requirements are skipped
    supabase_local = get_setting_value(profile.settings, "database", "supabase_local")

    # Check provider-specific requirements
    for category, providers in PROVIDER_REQUIREMENTS.items():
        provider_value = getattr(profile.providers, category)
        required_settings = providers.get(provider_value, [])

        for setting_key in required_settings:
            # Skip cloud-only Supabase requirements when supabase_local=true
            if (
                supabase_local
                and provider_value == "supabase"
                and setting_key
                in (
                    "supabase_project_ref",
                    "supabase_db_password",
                )
            ):
                continue
            value = get_setting_value(profile.settings, category, setting_key)
            if value is None or value == "":
                errors.append(
                    f"providers.{category}={provider_value} requires "
                    f"settings.{category}.{setting_key}"
                )

    # Check coherence rules
    for cat1, val1, cat2, _val2, required in COHERENCE_RULES:
        if getattr(profile.providers, cat1) == val1:
            # supabase_local satisfies Supabase cross-provider coherence
            if supabase_local and val1 == "supabase":
                continue
            # Check if the required config is present
            has_required = any(
                get_setting_value(profile.settings, cat2, key) is not None for key in required
            )
            if not has_required:
                errors.append(
                    f"providers.{cat1}={val1} requires {cat2} configuration ({', '.join(required)})"
                )

    return errors


def validate_profile_strict(
    profile_name: str,
    profiles_dir: Path | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Validate a profile including secret resolution.

    Args:
        profile_name: Name of profile to validate
        profiles_dir: Optional profiles directory override

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # First, validate structure (skip interpolation)
    try:
        profile = load_profile(profile_name, profiles_dir=profiles_dir, skip_interpolation=True)
    except ProfileError as e:
        errors.append(str(e))
        return False, errors, warnings

    # Validate provider requirements
    validation_errors = validate_profile(profile, check_secrets=False)
    errors.extend(validation_errors)

    # Try full loading with interpolation to check for missing vars
    try:
        load_profile(profile_name, profiles_dir=profiles_dir, skip_interpolation=False)
    except ProfileResolutionError as e:
        # Missing secrets are warnings for template validation
        warnings.append(f"Missing secret: {e.variable}")
    except ProfileError as e:
        errors.append(str(e))

    return len(errors) == 0, errors, warnings
