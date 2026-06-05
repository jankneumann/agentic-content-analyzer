"""Tests for the shared Railway CLI helper (`src/cli/railway.py`)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest
import typer

from src.cli import railway

# ─── ensure_railway_cli / set_variable ─────────────────────────────


def test_set_variable_missing_cli_raises_with_hint(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(typer.Exit):
        railway.set_variable("KEY", "value")
    assert "railway CLI not found" in capsys.readouterr().err


def test_set_variable_invokes_subprocess_with_correct_args(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    railway.set_variable("MY_KEY", "my-value")
    assert captured["cmd"] == ["railway", "variables", "--set", "MY_KEY=my-value"]


def test_set_variable_surfaces_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="not linked")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(typer.Exit):
        railway.set_variable("K", "v")


# ─── set_variables (batched) ───────────────────────────────────────


def test_set_variables_batches_into_single_call(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    railway.set_variables({"A": "1", "B": "2"}, service="api", environment="production")
    cmd = captured["cmd"]
    assert cmd[:2] == ["railway", "variables"]
    assert "--set" in cmd and "A=1" in cmd and "B=2" in cmd
    assert cmd[-4:] == ["--service", "api", "--environment", "production"]


def test_set_variables_empty_is_noop(monkeypatch):
    called = False

    def fake_run(*a, **k):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", fake_run)
    railway.set_variables({})
    assert called is False


# ─── get_variables ─────────────────────────────────────────────────


def test_get_variables_returns_empty_when_cli_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert railway.get_variables() == {}


def test_get_variables_parses_json(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"A": "1", "B": "2"}', stderr=""
        ),
    )
    assert railway.get_variables(service="api") == {"A": "1", "B": "2"}


def test_get_variables_returns_empty_on_bad_json(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not json", stderr=""
        ),
    )
    assert railway.get_variables() == {}


# ─── linked_target ─────────────────────────────────────────────────


def test_linked_target_parses_project_and_environment(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"name": "aca-prod", "environment": {"name": "production"}}',
            stderr="",
        ),
    )
    assert railway.linked_target() == "aca-prod / production"
