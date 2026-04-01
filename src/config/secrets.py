"""Secrets loading and masking for profile-based configuration.

This module provides:
- Loading secrets from .secrets.yaml file
- SecretValue wrapper for masking in logs/output
- Resolution order: env vars -> secrets file -> defaults
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# Import exception from profiles module
from src.config.profiles import SecretsParseError

# Default secrets file location
DEFAULT_SECRETS_FILE = ".secrets.yaml"

# Patterns for identifying secrets by key name
SECRET_KEY_PATTERNS = [
    re.compile(r".*_KEY$", re.IGNORECASE),
    re.compile(r".*_SECRET$", re.IGNORECASE),
    re.compile(r".*_PASSWORD$", re.IGNORECASE),
    re.compile(r".*_TOKEN$", re.IGNORECASE),
    re.compile(r".*_CREDENTIAL.*", re.IGNORECASE),
]

# Pattern for detecting credentials in URLs
URL_CREDENTIAL_PATTERN = re.compile(r"://[^:]+:([^@]+)@")


class SecretValue:
    """Wrapper for secret values that masks them in string representation.

    This class wraps a secret string and ensures it's masked when:
    - Converted to string (str())
    - Used in repr()
    - Logged

    The actual value is still accessible via the `.value` property.

    Example:
        >>> secret = SecretValue("my-api-key")
        >>> print(secret)
        ***
        >>> secret.value
        'my-api-key'
    """

    MASK = "***"

    def __init__(self, value: str, name: str | None = None):
        """Initialize a secret value.

        Args:
            value: The actual secret value
            name: Optional name/key for the secret (for debugging)
        """
        self._value = value
        self._name = name

    @property
    def value(self) -> str:
        """Get the actual secret value."""
        return self._value

    def __str__(self) -> str:
        """Return masked value for string conversion."""
        return self.MASK

    def __repr__(self) -> str:
        """Return masked representation."""
        if self._name:
            return f"SecretValue({self._name}={self.MASK})"
        return f"SecretValue({self.MASK})"

    def __eq__(self, other: object) -> bool:
        """Compare secret values."""
        if isinstance(other, SecretValue):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other
        return False

    def __hash__(self) -> int:
        """Hash based on value."""
        return hash(self._value)

    def __bool__(self) -> bool:
        """Return True if value is non-empty."""
        return bool(self._value)

    def __len__(self) -> int:
        """Return length of actual value."""
        return len(self._value)


def is_secret_key(key: str) -> bool:
    """Check if a key name indicates it contains a secret.

    Args:
        key: The key/variable name to check

    Returns:
        True if the key matches secret patterns
    """
    return any(pattern.match(key) for pattern in SECRET_KEY_PATTERNS)


def mask_url_credentials(url: str) -> str:
    """Mask credentials in a URL.

    Args:
        url: URL that may contain credentials

    Returns:
        URL with password masked
    """
    return URL_CREDENTIAL_PATTERN.sub(r"://***:***@", url)


def contains_url_credentials(value: str) -> bool:
    """Check if a string contains URL credentials.

    Args:
        value: String to check

    Returns:
        True if the string contains URL credentials
    """
    return bool(URL_CREDENTIAL_PATTERN.search(value))


def get_secrets_path() -> Path:
    """Get the path to the secrets file.

    Returns:
        Path from SECRETS_FILE env var, or default .secrets.yaml
    """
    secrets_file = os.environ.get("SECRETS_FILE", DEFAULT_SECRETS_FILE)
    return Path(secrets_file)


def load_secrets(secrets_path: Path | None = None) -> dict[str, str]:
    """Load secrets from .secrets.yaml file.

    Args:
        secrets_path: Optional path to secrets file (defaults to .secrets.yaml)

    Returns:
        Dictionary of secret key -> value mappings.
        Returns empty dict if file doesn't exist.

    Raises:
        SecretsParseError: If YAML is malformed
    """
    if secrets_path is None:
        secrets_path = get_secrets_path()

    if not secrets_path.exists():
        return {}

    try:
        with open(secrets_path) as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}

        if not isinstance(data, dict):
            raise SecretsParseError(message="Secrets file must be a YAML dictionary")

        # Convert all values to strings
        return {str(k): str(v) for k, v in data.items() if v is not None}

    except yaml.YAMLError as e:
        line = None
        if hasattr(e, "problem_mark") and e.problem_mark:
            line = e.problem_mark.line + 1
        raise SecretsParseError(line, str(e)) from e


def resolve_secret(
    key: str,
    secrets: dict[str, str] | None = None,
    default: str | None = None,
) -> str | None:
    """Resolve a secret value with precedence order.

    Resolution order (highest to lowest priority):
    1. Environment variable
    2. OpenBao KV v2 (when BAO_ADDR is configured)
    3. Secrets file (.secrets.yaml)
    4. Default value

    Args:
        key: The secret key to look up
        secrets: Pre-loaded secrets dict (loads from file if None)
        default: Default value if not found

    Returns:
        The resolved value, or default if not found
    """
    # Check environment first (highest priority)
    env_value = os.environ.get(key)
    if env_value is not None:
        return env_value

    # Check OpenBao (when configured)
    from src.config.bao_secrets import get_bao_secret

    bao_value = get_bao_secret(key)
    if bao_value is not None:
        return bao_value

    # Check secrets file
    if secrets is None:
        secrets = load_secrets()

    if key in secrets:
        return secrets[key]

    # Return default
    return default


def mask_secrets_in_dict(
    data: dict[str, Any],
    secrets: dict[str, str] | None = None,
    secret_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Recursively mask secret values in a dictionary.

    Secrets are identified by:
    1. Keys matching SECRET_KEY_PATTERNS
    2. Keys present in secrets dict
    3. Keys in the explicit secret_keys set
    4. String values containing URL credentials

    Args:
        data: Dictionary to mask
        secrets: Secrets dict (values from this dict are considered secrets)
        secret_keys: Additional keys to treat as secrets

    Returns:
        New dictionary with secret values masked
    """
    if secrets is None:
        secrets = {}
    if secret_keys is None:
        secret_keys = set()

    # Combine known secret keys
    all_secret_keys = secret_keys | set(secrets.keys())

    result: dict[str, Any] = {}

    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = mask_secrets_in_dict(value, secrets, secret_keys)
        elif isinstance(value, list):
            result[key] = [
                (
                    mask_secrets_in_dict(item, secrets, secret_keys)
                    if isinstance(item, dict)
                    else item
                )
                for item in value
            ]
        elif isinstance(value, str):
            # Check if this should be masked
            should_mask = (
                key in all_secret_keys
                or is_secret_key(key)
                or value in secrets.values()
                or contains_url_credentials(value)
            )
            if should_mask:
                if contains_url_credentials(value):
                    result[key] = mask_url_credentials(value)
                else:
                    result[key] = SecretValue.MASK
            else:
                result[key] = value
        elif isinstance(value, SecretValue):
            result[key] = SecretValue.MASK
        else:
            result[key] = value

    return result
