"""CLI commands for profile management.

Usage:
    newsletter-cli profile list
    newsletter-cli profile show <name>
    newsletter-cli profile validate <name>
    newsletter-cli profile inspect
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

import typer

from src.config.profiles import (
    ProfileError,
    ProfileNotFoundError,
    get_profiles_dir,
    list_available_profiles,
    load_profile,
    validate_profile,
    validate_profile_strict,
)
from src.config.secrets import load_secrets, mask_secrets_in_dict

app = typer.Typer(
    name="profile",
    help="Manage configuration profiles",
    no_args_is_help=True,
)


def _get_active_profile_name() -> str | None:
    """Get the active profile name from environment."""
    return os.environ.get("PROFILE")


def _format_value(value: str | None, is_secret: bool = False) -> str:
    """Format a value for display, masking if secret."""
    if value is None:
        return str(typer.style("(not set)", fg=typer.colors.BRIGHT_BLACK))
    if is_secret:
        return str(typer.style("***", fg=typer.colors.YELLOW))
    return str(value)


@app.command("list")
def list_profiles(
    profiles_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            "-d",
            help="Profiles directory (default: profiles/)",
        ),
    ] = None,
) -> None:
    """List all available profiles.

    Shows profile names, inheritance, and descriptions.
    The currently active profile (from PROFILE env var) is marked.
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()

    profiles = list_available_profiles(profiles_dir)

    if not profiles:
        typer.echo(f"No profiles found in {profiles_dir}")
        typer.echo()
        typer.echo("To create a profile from your .env file:")
        typer.echo("  newsletter-cli profile migrate --dry-run")
        raise typer.Exit(0)

    active_name = _get_active_profile_name()

    typer.echo(f"Available profiles in {profiles_dir}:\n")

    for name in profiles:
        try:
            profile = load_profile(name, profiles_dir=profiles_dir, skip_interpolation=True)

            # Build display line
            prefix = "* " if name == active_name else "  "
            extends = f" (extends: {profile.extends})" if profile.extends else ""
            desc = f" - {profile.description}" if profile.description else ""

            if name == active_name:
                line = typer.style(f"{prefix}{name}{extends}{desc}", bold=True)
            else:
                line = f"{prefix}{name}{extends}{desc}"

            typer.echo(line)

        except ProfileError as e:
            typer.echo(f"  {name} - " + typer.style(f"Error: {e}", fg=typer.colors.RED))


@app.command("show")
def show_profile(
    name: Annotated[str, typer.Argument(help="Profile name to show")],
    profiles_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Profiles directory"),
    ] = None,
    show_secrets: Annotated[
        bool,
        typer.Option("--show-secrets", "-s", help="Show secret values (dangerous!)"),
    ] = False,
    raw: Annotated[
        bool,
        typer.Option("--raw", "-r", help="Show raw YAML without inheritance resolution"),
    ] = False,
) -> None:
    """Show profile settings with inheritance resolved.

    Displays all settings from the profile with secrets masked.
    Use --show-secrets to reveal secret values (use with caution).
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()

    try:
        if raw:
            import yaml

            from src.config.profiles import load_profile_raw

            data = load_profile_raw(name, profiles_dir)
            typer.echo(yaml.dump(data, default_flow_style=False, sort_keys=False))
            return

        # Load with inheritance but skip interpolation to show placeholders
        profile = load_profile(name, profiles_dir=profiles_dir, skip_interpolation=True)

        typer.echo(f"Profile: {typer.style(profile.name, bold=True)}")
        if profile.extends:
            typer.echo(f"Extends: {profile.extends}")
        if profile.description:
            typer.echo(f"Description: {profile.description}")
        typer.echo()

        # Show providers
        typer.echo(typer.style("Providers:", bold=True))
        typer.echo(f"  database: {profile.providers.database}")
        typer.echo(f"  neo4j: {profile.providers.neo4j}")
        typer.echo(f"  storage: {profile.providers.storage}")
        typer.echo(f"  observability: {profile.providers.observability}")
        typer.echo()

        # Show settings
        typer.echo(typer.style("Settings:", bold=True))
        settings_dict = profile.settings.model_dump()

        # Optionally mask secrets
        if not show_secrets:
            secrets = load_secrets()
            settings_dict = mask_secrets_in_dict(settings_dict, secrets)

        _print_dict(settings_dict, indent=2)

    except ProfileNotFoundError as e:
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        if e.available:
            typer.echo(f"Available profiles: {', '.join(e.available)}")
        raise typer.Exit(1)
    except ProfileError as e:
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)


def _print_dict(data: dict, indent: int = 0) -> None:
    """Recursively print a dictionary with indentation."""
    for key, value in data.items():
        prefix = " " * indent
        if isinstance(value, dict):
            typer.echo(f"{prefix}{key}:")
            _print_dict(value, indent + 2)
        elif isinstance(value, list):
            typer.echo(f"{prefix}{key}: {value}")
        elif value is None:
            typer.echo(f"{prefix}{key}: " + typer.style("(not set)", dim=True))
        else:
            typer.echo(f"{prefix}{key}: {value}")


@app.command("validate")
def validate_profile_cmd(
    name: Annotated[str, typer.Argument(help="Profile name to validate")],
    profiles_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Profiles directory"),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Also check for unresolved secret references"),
    ] = False,
) -> None:
    """Validate a profile for completeness and coherence.

    Checks:
    - Profile loads without errors
    - Inheritance resolves correctly
    - Provider-specific required settings are present
    - Coherence rules are satisfied

    With --strict, also warns about unresolved variable references.
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()

    try:
        if strict:
            is_valid, errors, warnings = validate_profile_strict(name, profiles_dir)

            if warnings:
                typer.echo(typer.style("Warnings:", fg=typer.colors.YELLOW))
                for warning in warnings:
                    typer.echo(f"  - {warning}")

            if errors:
                typer.echo(typer.style("Errors:", fg=typer.colors.RED))
                for error in errors:
                    typer.echo(f"  - {error}")
                raise typer.Exit(1)
            else:
                typer.echo(typer.style(f"Profile '{name}' is valid!", fg=typer.colors.GREEN))

        else:
            # Basic validation (structure only)
            profile = load_profile(name, profiles_dir=profiles_dir, skip_interpolation=True)
            errors = validate_profile(profile, check_secrets=False)

            if errors:
                typer.echo(typer.style(f"Profile '{name}' has errors:", fg=typer.colors.RED))
                for error in errors:
                    typer.echo(f"  - {error}")
                raise typer.Exit(1)
            else:
                typer.echo(typer.style(f"Profile '{name}' is valid!", fg=typer.colors.GREEN))

    except ProfileNotFoundError as e:
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)
    except ProfileError as e:
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)


@app.command("inspect")
def inspect_settings(
    show_secrets: Annotated[
        bool,
        typer.Option("--show-secrets", "-s", help="Show secret values (dangerous!)"),
    ] = False,
) -> None:
    """Show effective Settings with source annotations.

    Displays the final merged settings from:
    - Profile (if PROFILE env var set)
    - Secrets file (.secrets.yaml)
    - Environment variables
    - Default values

    Each value is annotated with its source.
    """
    from src.config.settings import Settings, get_active_profile_name

    active_profile = get_active_profile_name()

    typer.echo(typer.style("Effective Configuration", bold=True))
    typer.echo("=" * 40)

    if active_profile:
        typer.echo(f"Active profile: {typer.style(active_profile, bold=True)}")
    else:
        typer.echo("Active profile: " + typer.style("(none - using .env)", dim=True))
    typer.echo()

    try:
        settings = Settings()

        # Get settings as dict
        settings_dict = {
            "environment": settings.environment,
            "database_provider": settings.database_provider,
            "neo4j_provider": settings.neo4j_provider,
            "storage_provider": getattr(settings, "storage_provider", "local"),
            "observability_provider": settings.observability_provider,
            "database_url": settings._mask_url(settings.get_effective_database_url()),
            "neo4j_uri": settings.get_effective_neo4j_uri(),
            "redis_url": settings.redis_url,
        }

        # Add API keys (masked unless --show-secrets)
        api_keys = {
            "anthropic_api_key": settings.anthropic_api_key if show_secrets else "***",
            "openai_api_key": (settings.openai_api_key or "(not set)")
            if show_secrets
            else ("***" if settings.openai_api_key else "(not set)"),
            "google_api_key": (settings.google_api_key or "(not set)")
            if show_secrets
            else ("***" if settings.google_api_key else "(not set)"),
        }

        typer.echo(typer.style("Core Settings:", bold=True))
        for key, value in settings_dict.items():
            typer.echo(f"  {key}: {value}")

        typer.echo()
        typer.echo(typer.style("API Keys:", bold=True))
        for key, value in api_keys.items():
            typer.echo(f"  {key}: {value}")

    except ProfileError as e:
        typer.echo(typer.style(f"Profile error: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(typer.style(f"Configuration error: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(typer.style(f"Unexpected error loading settings: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)


# =============================================================================
# Migration Command
# =============================================================================


# Secret detection patterns
SECRET_KEY_PATTERNS = [
    "KEY",
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "CREDENTIAL",
]


def _is_secret_key(key: str, extra_patterns: list[str] | None = None) -> bool:
    """Check if a key name indicates a secret value."""
    patterns = SECRET_KEY_PATTERNS + (extra_patterns or [])
    key_upper = key.upper()
    return any(pattern in key_upper for pattern in patterns)


def _parse_env_file(env_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Parse a .env file into key-value pairs and comments.

    Returns:
        Tuple of (variables dict, comments dict keyed by variable name)
    """
    variables: dict[str, str] = {}
    comments: dict[str, str] = {}
    current_comment = ""

    with open(env_path) as f:
        for line in f:
            line = line.rstrip("\n\r")

            # Track comments for the next variable
            if line.startswith("#"):
                if current_comment:
                    current_comment += "\n" + line[1:].strip()
                else:
                    current_comment = line[1:].strip()
                continue

            # Skip empty lines (reset comment tracking)
            if not line.strip():
                current_comment = ""
                continue

            # Parse key=value (also handles "export KEY=value" syntax)
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                # Strip "export " prefix if present (common in shell-compatible .env files)
                if key.startswith("export "):
                    key = key[7:]
                value = value.strip()

                # Remove quotes from value
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]

                variables[key] = value
                if current_comment:
                    comments[key] = current_comment
                    current_comment = ""

    return variables, comments


def _detect_providers(variables: dict[str, str]) -> dict[str, str]:
    """Detect provider settings from environment variables."""
    providers = {}

    if "DATABASE_PROVIDER" in variables:
        providers["database"] = variables["DATABASE_PROVIDER"]
    if "NEO4J_PROVIDER" in variables:
        providers["neo4j"] = variables["NEO4J_PROVIDER"]
    if "STORAGE_PROVIDER" in variables:
        providers["storage"] = variables["STORAGE_PROVIDER"]
    elif "IMAGE_STORAGE_PROVIDER" in variables:
        providers["storage"] = variables["IMAGE_STORAGE_PROVIDER"]
    if "OBSERVABILITY_PROVIDER" in variables:
        providers["observability"] = variables["OBSERVABILITY_PROVIDER"]

    return providers


def _categorize_setting(key: str) -> str:
    """Categorize a setting by its prefix."""
    key_upper = key.upper()

    if key_upper.startswith(("DATABASE_", "SUPABASE_DB", "NEON_", "RAILWAY_DATABASE", "REDIS_")):
        return "database"
    if key_upper.startswith(("NEO4J_", "GRAPHITI_", "SEMAPHORE_")):
        return "neo4j"
    if key_upper.startswith(("STORAGE_", "IMAGE_", "AWS_", "S3_", "SUPABASE_STORAGE", "MINIO_")):
        return "storage"
    if key_upper.startswith(("OTEL_", "OPIK_", "BRAINTRUST_", "OBSERVABILITY_")):
        return "observability"
    if key_upper.endswith(("_API_KEY", "_KEY", "_SECRET")):
        return "api_keys"

    return "general"


@app.command("migrate")
def migrate_env(
    env_file: Annotated[
        Path,
        typer.Option("--env-file", "-e", help="Path to .env file (default: .env)"),
    ] = Path(".env"),
    output_profile: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output profile name (default: migrated)"),
    ] = "migrated",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print output without creating files"),
    ] = False,
    preserve_comments: Annotated[
        bool,
        typer.Option("--preserve-comments", help="Convert .env comments to YAML comments"),
    ] = True,
    secret_patterns: Annotated[
        str | None,
        typer.Option("--secret-patterns", help="Additional secret key patterns (comma-separated)"),
    ] = None,
) -> None:
    """Migrate .env file to profile + secrets format.

    Parses an existing .env file and generates:
    - profiles/{name}.yaml with non-secret settings
    - .secrets.yaml with detected secrets

    Secret detection is based on key patterns (KEY, SECRET, PASSWORD, TOKEN).
    Use --secret-patterns to add custom patterns.

    Examples:
        newsletter-cli profile migrate
        newsletter-cli profile migrate --env-file .env.production --output production
        newsletter-cli profile migrate --dry-run
    """
    import yaml

    if not env_file.exists():
        typer.echo(typer.style(f"Error: {env_file} not found", fg=typer.colors.RED))
        raise typer.Exit(1)

    # Parse extra secret patterns
    extra_patterns = []
    if secret_patterns:
        extra_patterns = [p.strip().upper() for p in secret_patterns.split(",")]

    # Parse .env file
    variables, comments = _parse_env_file(env_file)

    if not variables:
        typer.echo("No variables found in .env file")
        raise typer.Exit(0)

    typer.echo(f"Parsed {len(variables)} variables from {env_file}")

    # Detect providers
    providers = _detect_providers(variables)

    # Separate secrets from settings
    secrets: dict[str, str] = {}
    settings: dict[str, dict[str, str]] = {
        "database": {},
        "neo4j": {},
        "storage": {},
        "observability": {},
        "api_keys": {},
        "general": {},
    }

    for key, value in variables.items():
        # Skip provider settings (they go in providers section)
        if key.endswith("_PROVIDER"):
            continue

        # Detect if this is a secret
        is_secret = _is_secret_key(key, extra_patterns)

        if is_secret:
            secrets[key] = value
        else:
            category = _categorize_setting(key)
            settings[category][key.lower()] = value

    # Build profile YAML structure
    profile_data: dict[str, Any] = {
        "name": output_profile,
        "extends": "base",
        "description": f"Migrated from {env_file}",
    }

    if providers:
        profile_data["providers"] = providers

    # Build settings section
    profile_settings: dict[str, Any] = {}

    # Add general settings at top level
    if settings["general"]:
        for key, value in settings["general"].items():
            profile_settings[key] = value

    # Add categorized settings
    for category in ["database", "neo4j", "storage", "observability", "api_keys"]:
        if settings[category]:
            profile_settings[category] = {}
            for key, value in settings[category].items():
                # Replace actual secret values with ${VAR} references
                if _is_secret_key(key.upper(), extra_patterns):
                    profile_settings[category][key] = f"${{{key.upper()}}}"
                else:
                    profile_settings[category][key] = value

    if profile_settings:
        profile_data["settings"] = profile_settings

    # Generate YAML output
    profile_yaml = yaml.dump(profile_data, default_flow_style=False, sort_keys=False)
    secrets_yaml = yaml.dump(secrets, default_flow_style=False, sort_keys=False) if secrets else ""

    # Add comments if requested
    if preserve_comments and comments:
        # Add a header comment
        profile_yaml = f"# Migrated from {env_file}\n\n" + profile_yaml
        if secrets_yaml:
            secrets_yaml = (
                f"# Secrets migrated from {env_file}\n# DO NOT COMMIT THIS FILE\n\n" + secrets_yaml
            )

    if dry_run:
        typer.echo()
        typer.echo(typer.style(f"=== profiles/{output_profile}.yaml ===", bold=True))
        typer.echo(profile_yaml)

        if secrets:
            typer.echo()
            typer.echo(typer.style("=== .secrets.yaml ===", bold=True))
            typer.echo(secrets_yaml)

        typer.echo()
        typer.echo(typer.style("(Dry run - no files created)", fg=typer.colors.YELLOW))
    else:
        # Create profile file
        profiles_dir = get_profiles_dir()
        profiles_dir.mkdir(exist_ok=True)

        profile_path = profiles_dir / f"{output_profile}.yaml"
        with open(profile_path, "w") as f:
            f.write(profile_yaml)
        typer.echo(f"Created: {profile_path}")

        # Create secrets file
        if secrets:
            secrets_path = Path(".secrets.yaml")
            if secrets_path.exists():
                typer.echo(
                    typer.style(
                        f"Warning: {secrets_path} already exists, not overwriting",
                        fg=typer.colors.YELLOW,
                    )
                )
            else:
                with open(secrets_path, "w") as f:
                    f.write(secrets_yaml)
                typer.echo(f"Created: {secrets_path}")

        typer.echo()
        typer.echo(typer.style("Migration complete!", fg=typer.colors.GREEN))
        typer.echo(f"To use the new profile: export PROFILE={output_profile}")


if __name__ == "__main__":
    app()
