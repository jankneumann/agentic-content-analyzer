"""Integration tests for OpenBao + Settings + resolve_secret() chain.

Covers spec scenarios openbao-secrets.15 (settings chain), .3 (env override),
.1 (graceful degradation), .2 (resolution), .16 (cache isolation), .19 (partial),
.23 (exception isolation).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.config.bao_secrets import clear_bao_cache
from src.config.secrets import resolve_secret


@pytest.fixture(autouse=True)
def _clean_bao():
    """Clear OpenBao cache before/after each test."""
    clear_bao_cache()
    yield
    clear_bao_cache()


def _mock_vault(secrets: dict[str, str]):
    """Context manager that mocks hvac to return given secrets."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": secrets}
    }
    mock_hvac = MagicMock()
    mock_hvac.Client.return_value = mock_client
    return patch("src.config.bao_secrets.hvac", mock_hvac, create=True)


# =========================================================================
# resolve_secret() with OpenBao tier (spec .2, .3, .16, .19)
# =========================================================================


class TestResolveSecretWithBao:
    """Verify resolve_secret() integrates OpenBao correctly."""

    def test_resolves_from_vault(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .2: resolve_secret() returns value from OpenBao."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with _mock_vault({"ANTHROPIC_API_KEY": "sk-from-vault"}):
            result = resolve_secret("ANTHROPIC_API_KEY", secrets={})

        assert result == "sk-from-vault"

    def test_env_var_overrides_vault(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .3: Env var wins over OpenBao."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.setenv("MY_KEY", "from-env")

        with _mock_vault({"MY_KEY": "from-vault"}):
            result = resolve_secret("MY_KEY", secrets={})

        assert result == "from-env"

    def test_vault_overrides_secrets_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenBao wins over .secrets.yaml."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.delenv("MY_KEY", raising=False)

        file_secrets = {"MY_KEY": "from-file"}

        with _mock_vault({"MY_KEY": "from-vault"}):
            result = resolve_secret("MY_KEY", secrets=file_secrets)

        assert result == "from-vault"

    def test_partial_response_falls_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .19: Missing vault key falls through to secrets file."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.delenv("MISSING_KEY", raising=False)

        file_secrets = {"MISSING_KEY": "from-file"}

        with _mock_vault({"OTHER_KEY": "other"}):
            result = resolve_secret("MISSING_KEY", secrets=file_secrets)

        assert result == "from-file"

    def test_cache_isolation_after_clear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .16: After clear_bao_cache(), re-fetches from vault."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.delenv("K", raising=False)

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.side_effect = [
            {"data": {"data": {"K": "v1"}}},
            {"data": {"data": {"K": "v2"}}},
        ]
        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            first = resolve_secret("K", secrets={})
            assert first == "v1"

            clear_bao_cache()
            second = resolve_secret("K", secrets={})
            assert second == "v2"


# =========================================================================
# Graceful degradation in resolve_secret() (spec .1)
# =========================================================================


class TestResolveSecretDegradation:
    """Verify resolve_secret() works without OpenBao."""

    def test_no_bao_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .1: Without BAO_ADDR, resolves from secrets file."""
        monkeypatch.delenv("BAO_ADDR", raising=False)
        monkeypatch.delenv("MY_KEY", raising=False)

        result = resolve_secret("MY_KEY", secrets={"MY_KEY": "from-file"})
        assert result == "from-file"

    def test_full_chain_env_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .3/.15: Full chain: env > vault > file > default."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.setenv("MY_KEY", "from-env")

        with _mock_vault({"MY_KEY": "from-vault"}):
            result = resolve_secret(
                "MY_KEY",
                secrets={"MY_KEY": "from-file"},
                default="default-value",
            )

        assert result == "from-env"

    def test_default_when_nowhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls through to default when not in any source."""
        monkeypatch.delenv("BAO_ADDR", raising=False)
        monkeypatch.delenv("NOWHERE", raising=False)

        result = resolve_secret("NOWHERE", secrets={}, default="fallback")
        assert result == "fallback"
