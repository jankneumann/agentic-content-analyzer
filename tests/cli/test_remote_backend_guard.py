"""Tests for the split-brain guard: is_remote_backend() + guard_remote_backend()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.output import guard_remote_backend, is_remote_backend

runner = CliRunner()


def _settings(api_base_url: str) -> MagicMock:
    return MagicMock(api_base_url=api_base_url)


class TestIsRemoteBackend:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://0.0.0.0:8000",
        ],
    )
    @patch("src.config.settings.get_settings")
    def test_local_urls_are_not_remote(self, mock_get: MagicMock, url: str) -> None:
        mock_get.return_value = _settings(url)
        assert is_remote_backend() is False

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.aca.rotkohl.ai",
            "https://staging.example.up.railway.app",
            "http://10.0.0.5:8000",
        ],
    )
    @patch("src.config.settings.get_settings")
    def test_remote_urls_are_remote(self, mock_get: MagicMock, url: str) -> None:
        mock_get.return_value = _settings(url)
        assert is_remote_backend() is True


class TestGuardRemoteBackend:
    @patch("src.config.settings.get_settings")
    def test_noop_when_local(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _settings("http://localhost:8000")
        # Should not raise.
        guard_remote_backend("kb list")

    @patch("src.config.settings.get_active_profile_name", return_value="railway-cli")
    @patch("src.config.settings.get_settings")
    def test_exits_when_remote(self, mock_get: MagicMock, _profile: MagicMock) -> None:
        mock_get.return_value = _settings("https://api.aca.rotkohl.ai")
        with pytest.raises(typer.Exit) as exc:
            guard_remote_backend("agent task")
        assert exc.value.exit_code == 1

    @patch("src.config.settings.get_active_profile_name", return_value="railway-cli")
    @patch("src.config.settings.get_settings")
    def test_message_includes_hint_and_profile(
        self, mock_get: MagicMock, _profile: MagicMock, capsys
    ) -> None:
        mock_get.return_value = _settings("https://api.aca.rotkohl.ai")
        with pytest.raises(typer.Exit):
            guard_remote_backend("manage backfill-chunks", http_hint="use --remote-db")
        err = capsys.readouterr().err
        assert "railway-cli" in err
        assert "manage backfill-chunks" in err
        assert "use --remote-db" in err


class TestCommandGuardsUnderRemoteProfile:
    """Direct-only DB commands must fail loud (not silently hit local DB)."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["kb", "list"],
            ["kb", "index"],
            ["kb", "show", "some-slug"],
            ["graph", "query", "-q", "anything"],
            ["jobs", "history"],
        ],
    )
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_commands_fail_loud_when_remote(self, _remote: MagicMock, argv: list[str]) -> None:
        result = runner.invoke(app, argv)
        assert result.exit_code == 1
        assert "Refusing to run" in result.output

    @pytest.mark.parametrize(
        "argv",
        [["kb", "list"], ["graph", "query"], ["jobs", "history"]],
    )
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_help_still_works_when_remote(self, _remote: MagicMock, argv: list[str]) -> None:
        # --help must short-circuit before the guard runs.
        result = runner.invoke(app, [*argv, "--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output
