"""Tests for secrets loading and masking."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.config.profiles import SecretsParseError
from src.config.secrets import (
    SecretValue,
    contains_url_credentials,
    is_secret_key,
    load_secrets,
    mask_secrets_in_dict,
    mask_url_credentials,
    resolve_secret,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_secrets_file(tmp_path: Path) -> Path:
    """Create a temporary secrets file."""
    secrets_path = tmp_path / ".secrets.yaml"
    return secrets_path


@pytest.fixture
def sample_secrets() -> dict[str, str]:
    """Sample secrets for testing."""
    return {
        "API_KEY": "sk-test-12345",
        "DATABASE_PASSWORD": "supersecret",
        "NEO4J_AURADB_PASSWORD": "aura-password",
    }


# =============================================================================
# SecretValue Tests
# =============================================================================


class TestSecretValue:
    """Tests for SecretValue wrapper class."""

    def test_value_access(self) -> None:
        """Test accessing the actual secret value."""
        secret = SecretValue("my-secret-key")
        assert secret.value == "my-secret-key"

    def test_str_returns_mask(self) -> None:
        """Test that str() returns masked value."""
        secret = SecretValue("my-secret-key")
        assert str(secret) == "***"
        assert "my-secret-key" not in str(secret)

    def test_repr_returns_mask(self) -> None:
        """Test that repr() returns masked value."""
        secret = SecretValue("my-secret-key")
        assert "***" in repr(secret)
        assert "my-secret-key" not in repr(secret)

    def test_repr_with_name(self) -> None:
        """Test repr with named secret."""
        secret = SecretValue("my-secret-key", name="API_KEY")
        assert "API_KEY" in repr(secret)
        assert "***" in repr(secret)
        assert "my-secret-key" not in repr(secret)

    def test_equality_with_secret_value(self) -> None:
        """Test equality comparison between SecretValues."""
        secret1 = SecretValue("same-value")
        secret2 = SecretValue("same-value")
        secret3 = SecretValue("different-value")

        assert secret1 == secret2
        assert secret1 != secret3

    def test_equality_with_string(self) -> None:
        """Test equality comparison with plain string."""
        secret = SecretValue("my-value")
        assert secret == "my-value"
        assert secret != "other-value"

    def test_bool_non_empty(self) -> None:
        """Test bool for non-empty secret."""
        secret = SecretValue("value")
        assert bool(secret) is True

    def test_bool_empty(self) -> None:
        """Test bool for empty secret."""
        secret = SecretValue("")
        assert bool(secret) is False

    def test_len(self) -> None:
        """Test length returns actual value length."""
        secret = SecretValue("12345")
        assert len(secret) == 5

    def test_hash(self) -> None:
        """Test that SecretValue can be used in sets/dicts."""
        secret1 = SecretValue("value")
        secret2 = SecretValue("value")

        # Same value should have same hash
        assert hash(secret1) == hash(secret2)

        # Can be used in set
        secret_set = {secret1, secret2}
        assert len(secret_set) == 1


# =============================================================================
# Secret Key Detection Tests
# =============================================================================


class TestIsSecretKey:
    """Tests for secret key pattern detection."""

    def test_api_key_patterns(self) -> None:
        """Test detection of *_KEY patterns."""
        assert is_secret_key("API_KEY")
        assert is_secret_key("OPENAI_API_KEY")
        assert is_secret_key("anthropic_api_key")  # Case insensitive

    def test_secret_patterns(self) -> None:
        """Test detection of *_SECRET patterns."""
        assert is_secret_key("AWS_SECRET")
        assert is_secret_key("CLIENT_SECRET")

    def test_password_patterns(self) -> None:
        """Test detection of *_PASSWORD patterns."""
        assert is_secret_key("DATABASE_PASSWORD")
        assert is_secret_key("NEO4J_PASSWORD")

    def test_token_patterns(self) -> None:
        """Test detection of *_TOKEN patterns."""
        assert is_secret_key("ACCESS_TOKEN")
        assert is_secret_key("REFRESH_TOKEN")

    def test_credential_patterns(self) -> None:
        """Test detection of *_CREDENTIAL* patterns."""
        assert is_secret_key("AWS_CREDENTIALS")
        assert is_secret_key("GOOGLE_CREDENTIAL_FILE")

    def test_non_secret_keys(self) -> None:
        """Test that non-secret keys are not flagged."""
        assert not is_secret_key("DATABASE_URL")
        assert not is_secret_key("LOG_LEVEL")
        assert not is_secret_key("ENVIRONMENT")


# =============================================================================
# URL Credential Tests
# =============================================================================


class TestUrlCredentials:
    """Tests for URL credential detection and masking."""

    def test_detects_url_with_password(self) -> None:
        """Test detection of URL with credentials."""
        url = "postgresql://user:password@localhost/db"
        assert contains_url_credentials(url)

    def test_no_credentials_in_url(self) -> None:
        """Test URL without credentials is not flagged."""
        url = "postgresql://localhost/db"
        assert not contains_url_credentials(url)

    def test_mask_url_credentials(self) -> None:
        """Test masking credentials in URL."""
        url = "postgresql://admin:supersecret@localhost:5432/mydb"
        masked = mask_url_credentials(url)
        assert "supersecret" not in masked
        assert "admin" not in masked
        assert "localhost:5432/mydb" in masked
        assert "***" in masked


# =============================================================================
# Load Secrets Tests
# =============================================================================


class TestLoadSecrets:
    """Tests for loading secrets from file."""

    def test_load_secrets_from_file(
        self, temp_secrets_file: Path, sample_secrets: dict[str, str]
    ) -> None:
        """Test loading secrets from YAML file."""
        with open(temp_secrets_file, "w") as f:
            yaml.dump(sample_secrets, f)

        secrets = load_secrets(temp_secrets_file)

        assert secrets["API_KEY"] == "sk-test-12345"
        assert secrets["DATABASE_PASSWORD"] == "supersecret"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Test that missing file returns empty dict."""
        nonexistent = tmp_path / "nonexistent.yaml"
        secrets = load_secrets(nonexistent)
        assert secrets == {}

    def test_empty_file_returns_empty(self, temp_secrets_file: Path) -> None:
        """Test that empty file returns empty dict."""
        temp_secrets_file.touch()
        secrets = load_secrets(temp_secrets_file)
        assert secrets == {}

    def test_converts_values_to_strings(self, temp_secrets_file: Path) -> None:
        """Test that all values are converted to strings."""
        data = {
            "STRING_KEY": "value",
            "INT_KEY": 12345,
            "FLOAT_KEY": 3.14,
        }
        with open(temp_secrets_file, "w") as f:
            yaml.dump(data, f)

        secrets = load_secrets(temp_secrets_file)

        assert secrets["STRING_KEY"] == "value"
        assert secrets["INT_KEY"] == "12345"
        assert secrets["FLOAT_KEY"] == "3.14"

    def test_malformed_yaml_raises_error(self, temp_secrets_file: Path) -> None:
        """Test that malformed YAML raises SecretsParseError."""
        with open(temp_secrets_file, "w") as f:
            f.write("key: value\n  bad_indent: [unclosed")

        with pytest.raises(SecretsParseError) as exc_info:
            load_secrets(temp_secrets_file)

        # Should include line number
        assert exc_info.value.line is not None

    def test_non_dict_yaml_raises_error(self, temp_secrets_file: Path) -> None:
        """Test that non-dict YAML raises error."""
        with open(temp_secrets_file, "w") as f:
            yaml.dump(["item1", "item2"], f)

        with pytest.raises(SecretsParseError) as exc_info:
            load_secrets(temp_secrets_file)

        assert "dictionary" in str(exc_info.value).lower()

    def test_null_values_excluded(self, temp_secrets_file: Path) -> None:
        """Test that null values are not included."""
        data = {
            "HAS_VALUE": "value",
            "NULL_VALUE": None,
        }
        with open(temp_secrets_file, "w") as f:
            yaml.dump(data, f)

        secrets = load_secrets(temp_secrets_file)

        assert "HAS_VALUE" in secrets
        assert "NULL_VALUE" not in secrets


# =============================================================================
# Resolve Secret Tests
# =============================================================================


class TestResolveSecret:
    """Tests for secret resolution with precedence."""

    def test_env_var_takes_precedence(
        self, temp_secrets_file: Path, sample_secrets: dict[str, str]
    ) -> None:
        """Test environment variable takes precedence over file."""
        with open(temp_secrets_file, "w") as f:
            yaml.dump(sample_secrets, f)

        secrets = load_secrets(temp_secrets_file)

        with patch.dict(os.environ, {"API_KEY": "env-value"}):
            result = resolve_secret("API_KEY", secrets)

        assert result == "env-value"

    def test_secrets_file_fallback(self, sample_secrets: dict[str, str]) -> None:
        """Test fallback to secrets dict when env var not set."""
        # Ensure env var is not set
        os.environ.pop("API_KEY", None)

        result = resolve_secret("API_KEY", sample_secrets)
        assert result == "sk-test-12345"

    def test_default_fallback(self) -> None:
        """Test fallback to default when not in env or secrets."""
        os.environ.pop("NONEXISTENT_KEY", None)

        result = resolve_secret("NONEXISTENT_KEY", {}, default="default-value")
        assert result == "default-value"

    def test_none_when_not_found(self) -> None:
        """Test None returned when not found anywhere."""
        os.environ.pop("NONEXISTENT_KEY", None)

        result = resolve_secret("NONEXISTENT_KEY", {})
        assert result is None


# =============================================================================
# Mask Secrets in Dict Tests
# =============================================================================


class TestMaskSecretsInDict:
    """Tests for masking secrets in dictionaries."""

    def test_masks_by_key_pattern(self) -> None:
        """Test masking based on key patterns."""
        data = {
            "API_KEY": "sk-secret",
            "DATABASE_URL": "postgres://localhost",
        }

        masked = mask_secrets_in_dict(data)

        assert masked["API_KEY"] == "***"
        assert masked["DATABASE_URL"] == "postgres://localhost"

    def test_masks_known_secrets(self) -> None:
        """Test masking values from secrets dict."""
        data = {
            "config": {
                "key": "known-secret-value",
            },
        }
        secrets = {"SOME_KEY": "known-secret-value"}

        masked = mask_secrets_in_dict(data, secrets)

        assert masked["config"]["key"] == "***"

    def test_masks_url_credentials(self) -> None:
        """Test masking credentials in URLs."""
        data = {
            "database_url": "postgres://user:password@localhost/db",
        }

        masked = mask_secrets_in_dict(data)

        assert "password" not in masked["database_url"]
        assert "***" in masked["database_url"]

    def test_masks_nested_dicts(self) -> None:
        """Test masking in nested dictionaries."""
        data = {
            "level1": {
                "level2": {
                    "API_KEY": "secret",
                    "name": "test",
                },
            },
        }

        masked = mask_secrets_in_dict(data)

        assert masked["level1"]["level2"]["API_KEY"] == "***"
        assert masked["level1"]["level2"]["name"] == "test"

    def test_handles_lists(self) -> None:
        """Test masking in lists of dicts."""
        data = {
            "items": [
                {"API_KEY": "secret1"},
                {"name": "item2"},
            ],
        }

        masked = mask_secrets_in_dict(data)

        assert masked["items"][0]["API_KEY"] == "***"
        assert masked["items"][1]["name"] == "item2"

    def test_explicit_secret_keys(self) -> None:
        """Test masking with explicit secret keys."""
        data = {
            "custom_field": "should-be-masked",
            "normal_field": "visible",
        }

        masked = mask_secrets_in_dict(data, secret_keys={"custom_field"})

        assert masked["custom_field"] == "***"
        assert masked["normal_field"] == "visible"

    def test_masks_secret_value_objects(self) -> None:
        """Test that SecretValue objects are masked."""
        data = {
            "wrapped": SecretValue("secret"),
            "plain": "visible",
        }

        masked = mask_secrets_in_dict(data)

        assert masked["wrapped"] == "***"
        assert masked["plain"] == "visible"
