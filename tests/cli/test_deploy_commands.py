"""Tests for `aca deploy sync-secrets` (`src/cli/deploy_commands.py`).

All Railway I/O is mocked — these verify the dry-run/apply gating, allowlist
enforcement, classification, redaction, and JSON shape. No subprocess runs.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.deploy_commands import app, mask
from src.cli.output import _set_json_mode
from src.config.deploy_secrets import SecretMapping, ServiceMapping

runner = CliRunner()

# Local secret values the command will "resolve". ANTHROPIC maps 1:1; NEON maps
# to the Railway name DATABASE_URL (rename).
LOCAL_VALUES = {
    "ANTHROPIC_API_KEY": "sk-ant-aaaa1111",
    "NEON_DATABASE_URL": "postgres://user:pw@host/db",
}


def _mapping():
    return {
        "api": ServiceMapping(
            service="api",
            secrets=(
                SecretMapping("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
                SecretMapping("NEON_DATABASE_URL", "DATABASE_URL"),
            ),
        )
    }


@contextmanager
def _harness(remote: dict | None = None):
    """Patch the mapping, secret resolution, and all Railway I/O."""
    remote = {} if remote is None else remote
    with (
        patch("src.config.deploy_secrets.load_mapping", return_value=_mapping()),
        patch("src.config.secrets.resolve_secret", side_effect=lambda k: LOCAL_VALUES.get(k)),
        patch("src.cli.deploy_commands.get_variables", return_value=remote),
        patch("src.cli.deploy_commands.linked_target", return_value="aca-prod / production"),
        patch("src.cli.deploy_commands.set_variables") as set_vars,
    ):
        yield set_vars


# ─── mask ──────────────────────────────────────────────────────────


def test_mask_short_long_empty():
    assert mask("") == ""
    assert mask("abcd") == "••••"
    assert mask("sk-ant-aaaa1111") == "sk-…1111"


# ─── dry-run ───────────────────────────────────────────────────────


def test_dry_run_writes_nothing_and_redacts():
    with _harness() as set_vars:
        result = runner.invoke(app, ["sync-secrets", "--service", "api"])
    assert result.exit_code == 0, result.output
    set_vars.assert_not_called()
    assert "[new]" in result.output
    assert "Dry-run" in result.output
    # Redaction: masked previews present, raw secrets absent.
    assert "sk-…1111" in result.output
    assert "sk-ant-aaaa1111" not in result.output
    assert "postgres://user:pw@host/db" not in result.output


# ─── apply ─────────────────────────────────────────────────────────


def test_apply_writes_new_and_changed():
    # DATABASE_URL exists but differs (changed); ANTHROPIC absent (new).
    with _harness(remote={"DATABASE_URL": "postgres://OLD"}) as set_vars:
        result = runner.invoke(
            app,
            ["sync-secrets", "--service", "api", "--env", "production", "--apply", "--yes"],
        )
    assert result.exit_code == 0, result.output
    set_vars.assert_called_once()
    pushed = set_vars.call_args.args[0]
    assert pushed == {
        "ANTHROPIC_API_KEY": "sk-ant-aaaa1111",
        "DATABASE_URL": "postgres://user:pw@host/db",
    }
    assert set_vars.call_args.kwargs["environment"] == "production"


def test_apply_skips_unchanged():
    # ANTHROPIC already identical remotely -> only DATABASE_URL pushed.
    with _harness(remote={"ANTHROPIC_API_KEY": "sk-ant-aaaa1111"}) as set_vars:
        result = runner.invoke(
            app,
            ["sync-secrets", "--service", "api", "--env", "production", "--apply", "--yes"],
        )
    assert result.exit_code == 0, result.output
    pushed = set_vars.call_args.args[0]
    assert pushed == {"DATABASE_URL": "postgres://user:pw@host/db"}


def test_apply_requires_explicit_env():
    with _harness() as set_vars:
        result = runner.invoke(app, ["sync-secrets", "--service", "api", "--apply"])
    assert result.exit_code != 0
    assert "--apply requires an explicit --env" in result.output
    set_vars.assert_not_called()


def test_unknown_service_errors():
    with _harness() as set_vars:
        result = runner.invoke(app, ["sync-secrets", "--service", "nope"])
    assert result.exit_code != 0
    assert "not found in railway_secrets.yaml" in result.output
    set_vars.assert_not_called()


def test_only_filter_limits_scope():
    with _harness() as set_vars:
        result = runner.invoke(
            app,
            [
                "sync-secrets",
                "--service",
                "api",
                "--only",
                "ANTHROPIC_API_KEY",
                "--env",
                "production",
                "--apply",
                "--yes",
            ],
        )
    assert result.exit_code == 0, result.output
    pushed = set_vars.call_args.args[0]
    assert pushed == {"ANTHROPIC_API_KEY": "sk-ant-aaaa1111"}


def test_missing_local_value_is_skipped_not_pushed():
    # ANTHROPIC resolves to None -> skipped; only DATABASE_URL is a candidate.
    with patch.dict(LOCAL_VALUES, {"ANTHROPIC_API_KEY": ""}, clear=False), _harness() as set_vars:
        result = runner.invoke(app, ["sync-secrets", "--service", "api"])
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output
    set_vars.assert_not_called()


def test_unmanaged_remote_var_listed_not_touched():
    with _harness(remote={"SOME_OTHER_VAR": "x"}) as set_vars:
        result = runner.invoke(
            app,
            ["sync-secrets", "--service", "api", "--env", "production", "--apply", "--yes"],
        )
    assert result.exit_code == 0, result.output
    pushed = set_vars.call_args.args[0]
    assert "SOME_OTHER_VAR" not in pushed  # never modified


# ─── JSON output ───────────────────────────────────────────────────


def test_json_output_shape_and_redaction():
    try:
        _set_json_mode(True)
        with _harness() as set_vars:
            result = runner.invoke(app, ["sync-secrets", "--service", "api"])
    finally:
        _set_json_mode(False)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) >= {
        "service",
        "environment",
        "new",
        "changed",
        "unchanged",
        "skipped",
        "unmanaged",
        "applied",
    }
    assert payload["applied"] is False
    set_vars.assert_not_called()
    # No raw secret value anywhere in the JSON payload.
    assert "sk-ant-aaaa1111" not in result.output
    assert all("masked" in entry for entry in payload["new"])
