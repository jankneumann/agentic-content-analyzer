"""Tests for `aca auth` deploy-target safety notice.

auth is a control-plane command: it pushes OAuth tokens to Railway env vars
via the `railway` CLI, independent of the active profile's api_base_url. These
tests cover the notice that surfaces both sources of truth before a push.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from src.cli import auth_commands


class TestRailwayLinkedTarget:
    @patch("src.cli.auth_commands.shutil.which", return_value=None)
    def test_returns_none_when_cli_missing(self, _which: MagicMock) -> None:
        assert auth_commands._railway_linked_target() is None

    @patch("src.cli.auth_commands.subprocess.run")
    @patch("src.cli.auth_commands.shutil.which", return_value="/usr/bin/railway")
    def test_parses_project_and_environment(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"name": "aca-prod", "environment": {"name": "production"}}',
            stderr="",
        )
        assert auth_commands._railway_linked_target() == "aca-prod / production"

    @patch("src.cli.auth_commands.subprocess.run")
    @patch("src.cli.auth_commands.shutil.which", return_value="/usr/bin/railway")
    def test_returns_none_on_nonzero_exit(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="not linked"
        )
        assert auth_commands._railway_linked_target() is None

    @patch(
        "src.cli.auth_commands.subprocess.run", side_effect=subprocess.TimeoutExpired("railway", 15)
    )
    @patch("src.cli.auth_commands.shutil.which", return_value="/usr/bin/railway")
    def test_returns_none_on_timeout(self, _which: MagicMock, _run: MagicMock) -> None:
        assert auth_commands._railway_linked_target() is None


class TestWarnDeployTarget:
    @patch("src.cli.auth_commands._railway_linked_target", return_value="aca-prod / production")
    @patch("src.config.settings.get_settings")
    @patch("src.config.settings.get_active_profile_name", return_value="railway-cli")
    def test_surfaces_both_sources_of_truth(
        self,
        _profile: MagicMock,
        mock_settings: MagicMock,
        _linked: MagicMock,
        capsys,
    ) -> None:
        mock_settings.return_value = MagicMock(api_base_url="https://api.aca.rotkohl.ai")

        auth_commands._warn_deploy_target(service=None)

        out = capsys.readouterr().out
        assert "railway-cli" in out
        assert "https://api.aca.rotkohl.ai" in out
        assert "aca-prod / production" in out
        # The independence caveat must be explicit.
        assert "independent" in out.lower()

    @patch("src.cli.auth_commands._railway_linked_target", return_value=None)
    @patch("src.config.settings.get_settings")
    @patch("src.config.settings.get_active_profile_name", return_value=None)
    def test_handles_unknown_link(
        self,
        _profile: MagicMock,
        mock_settings: MagicMock,
        _linked: MagicMock,
        capsys,
    ) -> None:
        mock_settings.return_value = MagicMock(api_base_url="http://localhost:8000")

        auth_commands._warn_deploy_target(service="backend")

        out = capsys.readouterr().out
        assert "unknown" in out.lower()
        assert "backend" in out
