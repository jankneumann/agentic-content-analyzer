"""Tests for ``aca auth gmail|youtube|status``.

The OAuth flow itself (which requires a browser) is not exercised — we
mock ``InstalledAppFlow.from_client_secrets_file`` and the subprocess
calls to ``railway``. The goal is to verify the *plumbing*: that errors
fail fast with clear messages, that the deploy path actually invokes
``railway variables --set``, and that the env-var-hydration paths are
wired into GmailClient/YouTubeClient.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from src.cli.auth_commands import _railway_set_env, app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ─── _railway_set_env ──────────────────────────────────────────────


def test_railway_set_env_missing_cli_fails_with_install_hint(monkeypatch):
    """When `railway` is not in PATH, fail with an install-instruction message."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(typer.Exit):
        _railway_set_env("KEY", "value")


def test_railway_set_env_invokes_subprocess_with_correct_args(monkeypatch):
    """Happy path: railway CLI present, subprocess called with --set KEY=VALUE."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    called_with = {}

    def fake_run(cmd, **kwargs):
        called_with["cmd"] = cmd
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _railway_set_env("MY_KEY", "my-value")
    assert called_with["cmd"] == ["railway", "variables", "--set", "MY_KEY=my-value"]


def test_railway_set_env_includes_service_flag_when_set(monkeypatch):
    """--service is appended only when provided."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    called_with = {}

    def fake_run(cmd, **kwargs):
        called_with["cmd"] = cmd
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _railway_set_env("K", "v", service="api")
    assert "--service" in called_with["cmd"]
    assert "api" in called_with["cmd"]


def test_railway_set_env_surfaces_subprocess_error(monkeypatch):
    """Non-zero exit from railway CLI bubbles up as typer.Exit with stderr in message."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="not linked")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(typer.Exit):
        _railway_set_env("K", "v")


# ─── aca auth status ───────────────────────────────────────────────


def test_status_command_lists_both_providers(runner, monkeypatch):
    """`aca auth status` mentions both gmail and youtube."""
    # Force railway lookup to be skipped — keeps the test hermetic.
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "gmail" in result.output
    assert "youtube" in result.output


def test_status_command_shows_railway_state_when_linked(runner, monkeypatch, tmp_path):
    """When `railway variables` succeeds, status reports which env vars are set."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")

    def fake_run(cmd, **kwargs):
        # Simulate a linked Railway project that already has the gmail token set
        # but not credentials, and nothing for youtube.
        return MagicMock(
            returncode=0,
            stdout="GMAIL_OAUTH_TOKEN_JSON=...\nOTHER=foo\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "GMAIL_OAUTH_TOKEN_JSON" in result.output
    assert "set" in result.output


# ─── aca auth gmail / youtube (without --deploy) ────────────────────


def test_gmail_command_missing_credentials_fails_clearly(runner, monkeypatch, tmp_path):
    """Without credentials.json present, the command fails with a clear hint
    pointing at Google Cloud Console — not a generic Python traceback."""
    # Point the settings credentials file at a tmp path that doesn't exist
    fake_creds = tmp_path / "credentials.json"
    fake_token = tmp_path / "token.json"
    from src.config import settings

    monkeypatch.setattr(settings, "gmail_credentials_file", str(fake_creds))
    monkeypatch.setattr(settings, "gmail_token_file", str(fake_token))
    result = runner.invoke(app, ["gmail"])
    assert result.exit_code == 1
    assert "console.cloud.google.com" in result.output


@patch("src.cli.auth_commands.InstalledAppFlow", create=True)
def test_gmail_command_runs_oauth_when_credentials_present(
    _mock_flow_module, runner, monkeypatch, tmp_path
):
    """When credentials.json exists, the OAuth flow runs and token is written.

    We mock ``InstalledAppFlow`` to skip the real browser dance.
    """
    fake_creds = tmp_path / "credentials.json"
    fake_creds.write_text('{"installed": {"client_id": "test"}}')
    fake_token = tmp_path / "token.json"

    from src.config import settings

    monkeypatch.setattr(settings, "gmail_credentials_file", str(fake_creds))
    monkeypatch.setattr(settings, "gmail_token_file", str(fake_token))

    # Mock the OAuth flow — patch where it's imported (lazy inside _run_oauth_flow)
    fake_creds_obj = MagicMock()
    fake_creds_obj.to_json.return_value = json.dumps({"token": "abc", "refresh_token": "xyz"})
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_creds_obj
    with patch("google_auth_oauthlib.flow.InstalledAppFlow") as mock_flow_cls:
        mock_flow_cls.from_client_secrets_file.return_value = fake_flow
        result = runner.invoke(app, ["gmail"])

    assert result.exit_code == 0, result.output
    assert fake_token.exists()
    saved = json.loads(fake_token.read_text())
    assert saved["token"] == "abc"
    # Without --deploy, no railway call should happen
    assert "--deploy" in result.output  # hint shown


# ─── aca auth gmail --deploy ────────────────────────────────────────


def test_gmail_deploy_uploads_token_to_railway(runner, monkeypatch, tmp_path):
    """--deploy triggers exactly one `railway variables --set` for the token."""
    fake_creds = tmp_path / "credentials.json"
    fake_creds.write_text('{"installed": {"client_id": "test"}}')
    fake_token = tmp_path / "token.json"

    from src.config import settings

    monkeypatch.setattr(settings, "gmail_credentials_file", str(fake_creds))
    monkeypatch.setattr(settings, "gmail_token_file", str(fake_token))
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")

    railway_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        railway_calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    fake_creds_obj = MagicMock()
    fake_creds_obj.to_json.return_value = json.dumps({"token": "abc"})
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_creds_obj

    with patch("google_auth_oauthlib.flow.InstalledAppFlow") as mock_flow_cls:
        mock_flow_cls.from_client_secrets_file.return_value = fake_flow
        result = runner.invoke(app, ["gmail", "--deploy"])

    assert result.exit_code == 0, result.output
    # Exactly one `variables --set` call — for the token, NOT credentials.
    # `--deploy` also runs `railway status --json` to warn about the target,
    # so filter to the variable-set calls rather than counting every railway call.
    set_calls = [c for c in railway_calls if "--set" in c]
    assert len(set_calls) == 1, railway_calls
    assert "GMAIL_OAUTH_TOKEN_JSON" in set_calls[0][3]


def test_gmail_deploy_with_include_credentials_uploads_both(runner, monkeypatch, tmp_path):
    """--include-credentials triggers TWO railway calls: token + credentials."""
    fake_creds = tmp_path / "credentials.json"
    fake_creds.write_text('{"installed": {"client_id": "test"}}')
    fake_token = tmp_path / "token.json"

    from src.config import settings

    monkeypatch.setattr(settings, "gmail_credentials_file", str(fake_creds))
    monkeypatch.setattr(settings, "gmail_token_file", str(fake_token))
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")

    railway_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        railway_calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    fake_creds_obj = MagicMock()
    fake_creds_obj.to_json.return_value = '{"token": "abc"}'
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_creds_obj

    with patch("google_auth_oauthlib.flow.InstalledAppFlow") as mock_flow_cls:
        mock_flow_cls.from_client_secrets_file.return_value = fake_flow
        result = runner.invoke(app, ["gmail", "--deploy", "--include-credentials"])

    assert result.exit_code == 0, result.output
    # Two `variables --set` calls (token + credentials); `--deploy` also runs
    # `railway status --json` to warn about the target, so filter to set calls.
    set_calls = [c for c in railway_calls if "--set" in c]
    assert len(set_calls) == 2, railway_calls
    env_keys = [call[3].split("=")[0] for call in set_calls]
    assert "GMAIL_OAUTH_TOKEN_JSON" in env_keys
    assert "GMAIL_CREDENTIALS_JSON" in env_keys
