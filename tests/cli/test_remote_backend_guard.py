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


class TestRemoteDbOptIn:
    """`--remote-db` is the deliberate escape hatch: it turns the guard into a
    loud no-op (warning, not refusal) and implies --direct so a batch job runs
    in-process against the remote DB.
    """

    @patch("src.config.settings.get_settings")
    def test_remote_db_bypasses_guard_with_warning(self, mock_get: MagicMock, capsys) -> None:
        from src.cli.output import _set_remote_db

        mock_get.return_value = _settings("https://api.aca.rotkohl.ai")
        _set_remote_db(True)
        try:
            # Must NOT raise — the opt-in permits direct remote-DB execution.
            guard_remote_backend("manage backfill-chunks")
        finally:
            _set_remote_db(False)
        err = capsys.readouterr().err
        assert "REMOTE database" in err

    @patch("src.cli.adapters.search_graph_sync", return_value=[])
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_flag_implies_direct_and_bypasses(
        self, _remote: MagicMock, mock_search: MagicMock
    ) -> None:
        from src.cli.output import _set_direct_mode, _set_remote_db, is_direct_mode, is_remote_db

        try:
            result = runner.invoke(app, ["--remote-db", "graph", "query", "-q", "x"])
            assert result.exit_code == 0, result.output
            assert "Refusing to run" not in result.output
            assert "REMOTE database" in result.output
            assert is_remote_db() is True
            assert is_direct_mode() is True
            mock_search.assert_called_once()
        finally:
            _set_remote_db(False)
            _set_direct_mode(False)


class TestCommandGuardsUnderRemoteProfile:
    """Direct-only DB commands must fail loud (not silently hit local DB)."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["kb", "list"],
            ["kb", "index"],
            ["kb", "show", "some-slug"],
            ["graph", "query", "-q", "anything"],
            # Direct-only DB commands (no HTTP path) — must refuse, not hit local DB.
            ["agent", "status"],
            ["agent", "insights"],
            ["evaluate", "list-datasets"],
            ["edit", "content", "1", "--title", "x"],
            ["manage", "backfill-chunks"],
            ["manage", "extract-refs"],
        ],
    )
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_commands_fail_loud_when_remote(self, _remote: MagicMock, argv: list[str]) -> None:
        result = runner.invoke(app, argv)
        assert result.exit_code == 1
        assert "Refusing to run" in result.output

    @pytest.mark.parametrize(
        "argv",
        [
            # sync uses explicit --from/--to profiles; only the IMPLICIT path is unsafe.
            # Guard fires before any file access, so these paths are never touched.
            ["sync", "export", "aca-guard-test.jsonl"],
            ["sync", "obsidian", "aca-guard-vault"],
        ],
    )
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_sync_implicit_profile_fails_loud(self, _remote: MagicMock, argv: list[str]) -> None:
        # No --from-profile/--to-profile: would silently use the local DB.
        result = runner.invoke(app, argv)
        assert result.exit_code == 1
        assert "Refusing to run" in result.output

    @pytest.mark.parametrize(
        "argv",
        [["kb", "list"], ["graph", "query"]],
    )
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_help_still_works_when_remote(self, _remote: MagicMock, argv: list[str]) -> None:
        # --help must short-circuit before the guard runs.
        result = runner.invoke(app, [*argv, "--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output


class TestApiBackedDirectFlagGuard:
    """API-backed commands run direct via `--direct` or the ConnectError
    fallback. Both paths funnel through the guarded `_*_direct` helper, so
    `--direct` under a remote profile must refuse rather than use local data.
    """

    @pytest.mark.parametrize(
        "argv",
        [
            ["--direct", "prompts", "list"],
            ["--direct", "settings", "list"],
        ],
    )
    @patch("src.cli.output.is_remote_backend", return_value=True)
    def test_direct_flag_fails_loud_when_remote(self, _remote: MagicMock, argv: list[str]) -> None:
        result = runner.invoke(app, argv)
        assert result.exit_code == 1
        assert "Refusing to run" in result.output
