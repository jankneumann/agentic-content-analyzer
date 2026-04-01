"""Tests for OpenBao seeding script (scripts/bao_seed_newsletter.py).

Covers spec scenarios openbao-secrets.9 through .13 (seeding, shared keys,
AppRole, DB engine, dry run) plus error paths.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

# Import functions under test
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from bao_seed_newsletter import (
    seed_approle,
    seed_db_engine,
    seed_secrets,
    seed_shared_keys,
)


@pytest.fixture
def secrets_file(tmp_path: Path) -> Path:
    """Create a temporary .secrets.yaml."""
    secrets = {
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "OPENAI_API_KEY": "sk-test",
        "NEO4J_PASSWORD": "neo4j-pass",
    }
    path = tmp_path / ".secrets.yaml"
    path.write_text(yaml.dump(secrets))
    return path


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock hvac client."""
    client = MagicMock()
    client.is_authenticated.return_value = True
    return client


# =========================================================================
# Seeding (spec .9)
# =========================================================================


class TestSeedSecrets:
    """Verify secret seeding from .secrets.yaml."""

    def test_seeds_all_string_values(
        self, mock_client: MagicMock, secrets_file: Path
    ) -> None:
        """spec .9: Write all secrets to secret/newsletter/."""
        result = seed_secrets(mock_client, secrets_file, "secret", "newsletter")

        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        call_kwargs = (
            mock_client.secrets.kv.v2.create_or_update_secret.call_args
        )
        assert call_kwargs.kwargs["path"] == "newsletter"
        assert len(result) == 3

    def test_dry_run_no_write(
        self, mock_client: MagicMock, secrets_file: Path
    ) -> None:
        """spec .13: Dry run doesn't write to OpenBao."""
        result = seed_secrets(
            None, secrets_file, "secret", "newsletter", dry_run=True
        )

        assert len(result) == 3
        # mock_client shouldn't be called at all (client is None in dry run)

    def test_missing_file_exits(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """spec .9 error: Missing .secrets.yaml exits with error."""
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(SystemExit):
            seed_secrets(mock_client, missing, "secret", "newsletter")


# =========================================================================
# Shared Keys (spec .10)
# =========================================================================


class TestSeedSharedKeys:
    """Verify shared key seeding with merge semantics."""

    def test_merge_preserves_other_projects(
        self, mock_client: MagicMock
    ) -> None:
        """spec .10: Newsletter wins on conflict, other keys preserved."""
        # Existing shared secrets from coordinator
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "ANTHROPIC_API_KEY": "old-coordinator-key",
                    "COORDINATOR_ONLY_KEY": "coord-value",
                }
            }
        }

        secrets = {
            "ANTHROPIC_API_KEY": "new-newsletter-key",
            "OPENAI_API_KEY": "openai-key",
        }

        seed_shared_keys(
            mock_client,
            secrets,
            ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"],
            "secret",
        )

        written = mock_client.secrets.kv.v2.create_or_update_secret.call_args
        merged_data = written.kwargs["secret"]

        # Newsletter value wins
        assert merged_data["ANTHROPIC_API_KEY"] == "new-newsletter-key"
        # Coordinator key preserved
        assert merged_data["COORDINATOR_ONLY_KEY"] == "coord-value"
        # New newsletter key added
        assert merged_data["OPENAI_API_KEY"] == "openai-key"

    def test_dry_run_no_write(self, mock_client: MagicMock) -> None:
        """spec .13: Shared key dry run doesn't write."""
        secrets = {"KEY": "value"}
        seed_shared_keys(mock_client, secrets, ["KEY"], "secret", dry_run=True)
        mock_client.secrets.kv.v2.create_or_update_secret.assert_not_called()

    def test_missing_keys_warns(
        self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """spec .10: Missing keys produce a warning."""
        secrets = {"KEY_A": "value"}
        seed_shared_keys(
            mock_client, secrets, ["KEY_A", "MISSING_KEY"], "secret", dry_run=True
        )
        captured = capsys.readouterr()
        assert "MISSING_KEY" in captured.err


# =========================================================================
# AppRole Creation (spec .11)
# =========================================================================


class TestSeedAppRole:
    """Verify AppRole and policy creation."""

    def test_creates_policy_and_role(self, mock_client: MagicMock) -> None:
        """spec .11: Creates newsletter-read policy and newsletter-app role."""
        mock_client.sys.list_auth_methods.return_value = {"approle/": {}}
        mock_client.auth.approle.read_role_id.return_value = {
            "data": {"role_id": "test-role-id"}
        }

        seed_approle(mock_client, "secret", "newsletter", 3600)

        mock_client.sys.create_or_update_policy.assert_called_once()
        policy_call = mock_client.sys.create_or_update_policy.call_args
        assert policy_call.kwargs["name"] == "newsletter-read"
        assert "newsletter" in policy_call.kwargs["policy"]
        assert "shared" in policy_call.kwargs["policy"]

        mock_client.auth.approle.create_or_update_approle.assert_called_once()

    def test_dry_run_no_write(self, mock_client: MagicMock) -> None:
        """spec .13: AppRole dry run doesn't create anything."""
        seed_approle(None, "secret", "newsletter", 3600, dry_run=True)


# =========================================================================
# Database Engine (spec .12)
# =========================================================================


class TestSeedDbEngine:
    """Verify database secrets engine configuration."""

    def test_configures_postgres(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .12: Configures newsletter-postgres with 1h TTL."""
        monkeypatch.setenv(
            "POSTGRES_DSN",
            "postgresql://user:pass@localhost:5432/newsletters",
        )
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "database/": {}
        }

        seed_db_engine(mock_client)

        mock_client.secrets.database.create_role.assert_called_once()
        role_call = mock_client.secrets.database.create_role.call_args
        assert role_call.kwargs["name"] == "newsletter-app"
        assert role_call.kwargs["default_ttl"] == "1h"
        assert role_call.kwargs["max_ttl"] == "24h"

    def test_missing_dsn_exits(self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .12 error: No POSTGRES_DSN exits."""
        monkeypatch.delenv("POSTGRES_DSN", raising=False)
        with pytest.raises(SystemExit):
            seed_db_engine(mock_client)


# =========================================================================
# Failure Cases (spec .9 error paths)
# =========================================================================


class TestSeedingFailures:
    """Verify error handling in seeding operations."""

    def test_vault_write_failure(
        self, mock_client: MagicMock, secrets_file: Path
    ) -> None:
        """Vault write permission denied raises."""
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = (
            Exception("permission denied")
        )
        with pytest.raises(Exception, match="permission denied"):
            seed_secrets(mock_client, secrets_file, "secret", "newsletter")

    def test_shared_read_failure_creates_new(
        self, mock_client: MagicMock
    ) -> None:
        """If shared path doesn't exist yet, create from scratch."""
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "not found"
        )
        secrets = {"KEY": "value"}
        seed_shared_keys(mock_client, secrets, ["KEY"], "secret")

        # Should still write despite read failure
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        written = mock_client.secrets.kv.v2.create_or_update_secret.call_args
        assert written.kwargs["secret"] == {"KEY": "value"}
