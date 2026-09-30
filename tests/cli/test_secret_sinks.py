"""Tests for the ``aca auth --to`` secret sinks (``src/cli/secret_sinks.py``).

Network-free: OpenBao is a fake KV v2 client that models the server-side
merge-PATCH and refuses hvac's client-side ``patch``/``create_or_update_secret``;
Railway is a mocked ``set_variables`` or a fake ``subprocess.run``; the secrets
file lives under ``tmp_path``.
"""

from __future__ import annotations

import copy
import json
import logging
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from src.cli import secret_sinks
from src.cli.auth_commands import app
from src.cli.secret_sinks import (
    BaoSink,
    RailwaySink,
    SecretsFileSink,
    SecretSink,
    SecretSinkError,
    SinkName,
    build_sink,
)
from src.config.deploy_secrets import load_mapping

TOKEN_SENTINEL = "SENTINEL-TOKEN-VALUE-do-not-print"
FIXED_NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)


# ─── Fake OpenBao KV v2 ────────────────────────────────────────────────


class InvalidPath(Exception):  # noqa: N818 — must match hvac class name
    """Named like hvac.exceptions.InvalidPath (the sink classifies by name)."""


class Forbidden(Exception):  # noqa: N818 — must match hvac class name
    """Named like hvac.exceptions.Forbidden."""


class _RefusingKvV2:
    """hvac's kv.v2 surface: every full-document write path must stay unused."""

    def patch(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("hvac kv.v2.patch is client-side read+create_or_update; never use it")

    def create_or_update_secret(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("create_or_update_secret would clobber sibling keys")

    def read_secret_version(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("the workstation role cannot read; the sink must not need to")


class _FakeAdapter:
    def __init__(self, store: dict[tuple[str, str], dict[str, str]], forbidden: bool) -> None:
        self.store = store
        self.forbidden = forbidden
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append({"method": method, "url": url, "headers": headers, **kwargs})
        assert method == "PATCH"
        assert (headers or {}).get("Content-Type") == "application/merge-patch+json"
        prefix, _, rest = url.partition("/v1/")
        assert prefix == ""
        mount, _, path = rest.partition("/data/")
        if self.forbidden:
            raise Forbidden("1 error occurred: permission denied")
        if (mount, path) not in self.store:
            raise InvalidPath(f"no secret at {mount}/{path}")
        current = self.store[mount, path]
        for key, value in kwargs["json"]["data"].items():  # RFC 7386 merge patch
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
        return {"data": {"version": 2}}


class FakeHvacClient:
    def __init__(
        self,
        store: dict[tuple[str, str], dict[str, str]] | None = None,
        *,
        forbidden: bool = False,
    ) -> None:
        self.store = store if store is not None else {}
        self.adapter = _FakeAdapter(self.store, forbidden)
        self.secrets = MagicMock()
        self.secrets.kv.v2 = _RefusingKvV2()


def _seeded_store() -> dict[tuple[str, str], dict[str, str]]:
    return {
        ("secret", "newsletter"): {
            "ANTHROPIC_API_KEY": "sk-ant-sibling",
            "OPENAI_API_KEY": "sk-openai-sibling",
            "GMAIL_CREDENTIALS_JSON": '{"installed": {"client_id": "kept"}}',
            "MULTILINE": "line one\nline two\n",
            "UNICODE": "café ✓",
        }
    }


# ─── Protocol / factory ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        (SinkName.RAILWAY, RailwaySink),
        (SinkName.BAO, BaoSink),
        (SinkName.SECRETS_FILE, SecretsFileSink),
    ],
)
def test_build_sink_returns_protocol_implementations(name: SinkName, cls: type) -> None:
    sink = build_sink(name)
    assert isinstance(sink, cls)
    assert isinstance(sink, SecretSink)
    assert sink.name is name


@pytest.mark.parametrize("values", [{}, {"lower_case": "v"}, {"X-DASH": "v"}, {"OK": 1}])
def test_sinks_reject_empty_or_malformed_writes(values: dict[str, Any], tmp_path: Path) -> None:
    sink = SecretsFileSink(tmp_path / ".secrets.yaml")
    with pytest.raises(SecretSinkError):
        sink.write(values)
    assert not (tmp_path / ".secrets.yaml").exists()


# ─── BaoSink ───────────────────────────────────────────────────────────


def test_bao_sink_patches_only_named_key_and_saved_at() -> None:
    client = FakeHvacClient(_seeded_store())
    before = copy.deepcopy(client.store["secret", "newsletter"])
    sink = BaoSink(client=client, clock=lambda: FIXED_NOW)

    written = sink.write({"GMAIL_OAUTH_TOKEN_JSON": TOKEN_SENTINEL})

    assert written == ["GMAIL_OAUTH_TOKEN_JSON"]
    after = client.store["secret", "newsletter"]
    assert set(after) == set(before) | {
        "GMAIL_OAUTH_TOKEN_JSON",
        "GMAIL_OAUTH_TOKEN_JSON_SAVED_AT",
    }
    for key, value in before.items():
        assert after[key].encode() == value.encode(), key  # byte-identical siblings
    assert after["GMAIL_OAUTH_TOKEN_JSON"] == TOKEN_SENTINEL
    assert after["GMAIL_OAUTH_TOKEN_JSON_SAVED_AT"] == "2026-09-22T12:00:00+00:00"

    (call,) = client.adapter.calls
    assert call["url"] == "/v1/secret/data/newsletter"
    assert call["json"] == {
        "data": {
            "GMAIL_OAUTH_TOKEN_JSON": TOKEN_SENTINEL,
            "GMAIL_OAUTH_TOKEN_JSON_SAVED_AT": "2026-09-22T12:00:00+00:00",
        }
    }


def test_bao_sink_writes_multiple_keys_in_one_patch() -> None:
    client = FakeHvacClient(_seeded_store())
    sink = BaoSink(client=client, clock=lambda: FIXED_NOW)

    sink.write({"X_AUTH_TOKEN": "a", "X_CT0": "b"})

    assert len(client.adapter.calls) == 1
    data = client.adapter.calls[0]["json"]["data"]
    assert set(data) == {"X_AUTH_TOKEN", "X_AUTH_TOKEN_SAVED_AT", "X_CT0", "X_CT0_SAVED_AT"}


def test_bao_sink_honours_mount_and_path_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_MOUNT_PATH", "kv")
    monkeypatch.setenv("BAO_SECRET_PATH", "aca/prod")
    client = FakeHvacClient({("kv", "aca/prod"): {"OTHER": "x"}})
    sink = BaoSink(client=client, clock=lambda: FIXED_NOW)

    sink.write({"K": "v"})

    assert client.adapter.calls[0]["url"] == "/v1/kv/data/aca/prod"
    assert client.store["kv", "aca/prod"]["OTHER"] == "x"
    assert sink.target == "OpenBao kv/aca/prod"


def test_bao_sink_refuses_to_create_missing_path() -> None:
    client = FakeHvacClient({})  # nothing seeded
    sink = BaoSink(client=client)

    with pytest.raises(SecretSinkError) as excinfo:
        sink.write({"GMAIL_OAUTH_TOKEN_JSON": TOKEN_SENTINEL})

    message = str(excinfo.value)
    assert "does not exist" in message
    assert "seed" in message.lower()
    assert TOKEN_SENTINEL not in message
    assert client.store == {}


def test_bao_sink_reports_missing_patch_capability() -> None:
    client = FakeHvacClient(_seeded_store(), forbidden=True)
    sink = BaoSink(client=client)

    with pytest.raises(SecretSinkError, match="'patch' capability"):
        sink.write({"K": TOKEN_SENTINEL})


def test_bao_sink_check_requires_bao_addr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    with pytest.raises(SecretSinkError, match="BAO_ADDR"):
        BaoSink().check()


def test_bao_sink_check_explains_missing_hvac(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_ADDR", "http://127.0.0.1:8200")
    monkeypatch.setenv("BAO_TOKEN", "t")
    monkeypatch.setattr("src.config.bao_secrets.hvac", None)
    with pytest.raises(SecretSinkError, match=r"\.\[vault\]"):
        BaoSink().check()


def test_bao_sink_check_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_ADDR", "http://127.0.0.1:8200")
    for var in ("BAO_TOKEN", "BAO_ROLE_ID", "BAO_SECRET_ID"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("src.config.bao_secrets.hvac", MagicMock())
    with pytest.raises(SecretSinkError, match="BAO_TOKEN"):
        BaoSink().check()


def test_bao_sink_check_fails_when_not_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_ADDR", "http://127.0.0.1:8200")
    monkeypatch.setenv("BAO_TOKEN", "t")
    fake_hvac = MagicMock()
    fake_hvac.Client.return_value.is_authenticated.return_value = False
    monkeypatch.setattr("src.config.bao_secrets.hvac", fake_hvac)
    with pytest.raises(SecretSinkError, match="authentication"):
        BaoSink().check()


# ─── SecretsFileSink ───────────────────────────────────────────────────


def test_secrets_file_sink_updates_key_and_preserves_everything_else(tmp_path: Path) -> None:
    path = tmp_path / ".secrets.yaml"
    path.write_text(
        "# local secrets — YAML, never KEY=value\n"
        "ANTHROPIC_API_KEY: sk-ant-local\n"
        "\n"
        "# Gmail\n"
        "GMAIL_OAUTH_TOKEN_JSON: |\n"
        '  {"token": "old",\n'
        "\n"
        '   "refresh_token": "r"}\n'
        "OPENAI_API_KEY: 'sk-openai'  # trailing comment\n"
        "NUMBER: 42\n"
    )
    path.chmod(0o644)

    SecretsFileSink(path).write({"GMAIL_OAUTH_TOKEN_JSON": TOKEN_SENTINEL})

    text = path.read_text()
    assert "# local secrets — YAML, never KEY=value\n" in text
    assert "# Gmail\n" in text
    assert "# trailing comment" in text
    assert '"old"' not in text
    data = yaml.safe_load(text)
    assert data == {
        "ANTHROPIC_API_KEY": "sk-ant-local",
        "GMAIL_OAUTH_TOKEN_JSON": TOKEN_SENTINEL,
        "OPENAI_API_KEY": "sk-openai",
        "NUMBER": 42,
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_secrets_file_sink_appends_new_keys_and_creates_private_file(tmp_path: Path) -> None:
    path = tmp_path / ".secrets.yaml"
    sink = SecretsFileSink(path)

    sink.write({"X_AUTH_TOKEN": "a"})
    sink.write({"X_CT0": "b"})

    assert yaml.safe_load(path.read_text()) == {"X_AUTH_TOKEN": "a", "X_CT0": "b"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == [".secrets.yaml"]  # no temp leftovers


@pytest.mark.parametrize(
    "value",
    [
        json.dumps({"token": "a", "refresh_token": "b", "scopes": ["x:y"]}),
        "has: colon # and hash",
        "  leading and trailing spaces  ",
        "multi\nline\nvalue\n",
        "quotes ' and \" mixed",
        "unicode ✓ café",
        "yes",
        "",
    ],
)
def test_secrets_file_sink_round_trips_awkward_values(tmp_path: Path, value: str) -> None:
    path = tmp_path / ".secrets.yaml"
    path.write_text("A: 1\nTARGET: old\nZ: last\n")

    SecretsFileSink(path).write({"TARGET": value})

    assert yaml.safe_load(path.read_text()) == {"A": 1, "TARGET": value, "Z": "last"}


def test_secrets_file_sink_file_without_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / ".secrets.yaml"
    path.write_text("A: 1")

    SecretsFileSink(path).write({"B": "2"})

    assert yaml.safe_load(path.read_text()) == {"A": 1, "B": "2"}


def test_secrets_file_sink_falls_back_to_full_dump_for_exotic_yaml(tmp_path: Path) -> None:
    path = tmp_path / ".secrets.yaml"
    # A flow mapping spanning lines defeats the line editor; keys must survive.
    path.write_text("{A: 1,\nTARGET: old}\n")

    SecretsFileSink(path).write({"TARGET": "new"})

    assert yaml.safe_load(path.read_text()) == {"A": 1, "TARGET": "new"}


def test_secrets_file_sink_refuses_malformed_file(tmp_path: Path) -> None:
    path = tmp_path / ".secrets.yaml"
    original = "KEY=value\n- not: a mapping\n"
    path.write_text(original)

    with pytest.raises(SecretSinkError):
        SecretsFileSink(path).write({"K": "v"})
    assert path.read_text() == original


def test_secrets_file_sink_defaults_to_secrets_file_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETS_FILE", str(tmp_path / "custom.yaml"))
    assert SecretsFileSink().path == tmp_path / "custom.yaml"


# ─── RailwaySink ───────────────────────────────────────────────────────


def test_railway_sink_calls_set_variables_once_per_write(capsys: pytest.CaptureFixture) -> None:
    values = {"X_AUTH_TOKEN": TOKEN_SENTINEL + "-a", "X_CT0": TOKEN_SENTINEL + "-b"}
    with patch("src.cli.railway.set_variables") as mock_set:
        written = RailwaySink(service="api").write(values)

    mock_set.assert_called_once_with(values, service="api")
    assert written == ["X_AUTH_TOKEN", "X_CT0"]
    captured = capsys.readouterr()
    assert "Railway env var X_AUTH_TOKEN set on service api." in captured.out
    assert "Railway env var X_CT0 set on service api." in captured.out
    assert TOKEN_SENTINEL not in captured.out + captured.err


def test_railway_sink_check_requires_cli_and_prints_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("src.cli.railway.linked_target", lambda: "aca / production")
    monkeypatch.setattr("src.cli.railway.ensure_railway_cli", lambda: None)
    with patch("src.config.settings.get_active_profile_name", return_value="railway"):
        RailwaySink(service="worker").check()
    out = capsys.readouterr().out
    assert "aca / production" in out
    assert "worker" in out
    assert "independent" in out


# ─── CLI wiring ────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def oauth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point Gmail/YouTube credential files at tmp and fake the browser flow."""
    from src.config import settings

    for provider in ("gmail", "youtube"):
        creds = tmp_path / f"{provider}_credentials.json"
        creds.write_text('{"installed": {"client_id": "test"}}')
        monkeypatch.setattr(settings, f"{provider}_credentials_file", str(creds))
        monkeypatch.setattr(settings, f"{provider}_token_file", str(tmp_path / f"{provider}.json"))

    fake_creds = MagicMock()
    fake_creds.to_json.return_value = json.dumps({"token": TOKEN_SENTINEL})
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_creds
    with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow_cls:
        flow_cls.from_client_secrets_file.return_value = fake_flow
        yield flow_cls


def _use_fake_bao(monkeypatch: pytest.MonkeyPatch, client: FakeHvacClient) -> None:
    monkeypatch.setattr(secret_sinks, "_default_bao_client", lambda: client)


def test_cli_gmail_to_bao_writes_only_token_key(
    runner: CliRunner,
    oauth_env: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeHvacClient(_seeded_store())
    before = copy.deepcopy(client.store["secret", "newsletter"])
    _use_fake_bao(monkeypatch, client)

    with caplog.at_level(logging.DEBUG):
        result = runner.invoke(app, ["gmail", "--to", "bao"])

    assert result.exit_code == 0, result.output
    after = client.store["secret", "newsletter"]
    new_keys = set(after) - set(before)
    assert new_keys == {"GMAIL_OAUTH_TOKEN_JSON", "GMAIL_OAUTH_TOKEN_JSON_SAVED_AT"}
    assert {k: after[k] for k in before} == before
    assert json.loads(after["GMAIL_OAUTH_TOKEN_JSON"]) == {"token": TOKEN_SENTINEL}
    assert "GMAIL_OAUTH_TOKEN_JSON" in result.output
    assert "OpenBao secret/newsletter" in result.output
    assert TOKEN_SENTINEL not in result.output
    assert TOKEN_SENTINEL not in caplog.text


def test_cli_youtube_to_bao_needs_no_provider_specific_code(
    runner: CliRunner, oauth_env: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeHvacClient(_seeded_store())
    _use_fake_bao(monkeypatch, client)

    result = runner.invoke(app, ["youtube", "--to", "bao", "--include-credentials"])

    assert result.exit_code == 0, result.output
    after = client.store["secret", "newsletter"]
    assert "YOUTUBE_OAUTH_TOKEN_JSON" in after
    assert json.loads(after["YOUTUBE_CREDENTIALS_JSON"]) == {"installed": {"client_id": "test"}}
    assert after["GMAIL_CREDENTIALS_JSON"] == '{"installed": {"client_id": "kept"}}'


def test_cli_to_bao_fails_before_oauth_when_unconfigured(
    runner: CliRunner, oauth_env: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)

    result = runner.invoke(app, ["gmail", "--to", "bao"])

    assert result.exit_code == 1
    assert "BAO_ADDR" in result.output
    oauth_env.from_client_secrets_file.assert_not_called()


def test_cli_to_bao_missing_path_exits_nonzero_without_leaking(
    runner: CliRunner, oauth_env: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_fake_bao(monkeypatch, FakeHvacClient({}))

    result = runner.invoke(app, ["gmail", "--to", "bao"])

    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert TOKEN_SENTINEL not in result.output


def test_cli_to_secrets_file(
    runner: CliRunner, oauth_env: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secrets_path = tmp_path / ".secrets.yaml"
    secrets_path.write_text("ANTHROPIC_API_KEY: keep-me\n")
    monkeypatch.setenv("SECRETS_FILE", str(secrets_path))

    result = runner.invoke(app, ["gmail", "--to", "secrets-file"])

    assert result.exit_code == 0, result.output
    data = yaml.safe_load(secrets_path.read_text())
    assert data["ANTHROPIC_API_KEY"] == "keep-me"
    assert json.loads(data["GMAIL_OAUTH_TOKEN_JSON"]) == {"token": TOKEN_SENTINEL}
    assert TOKEN_SENTINEL not in result.output


def _railway_argv(runner: CliRunner, monkeypatch: pytest.MonkeyPatch, args: list[str]):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.invoke(app, args)
    return result, [c for c in calls if "--set" in c]


def test_cli_deploy_is_deprecated_alias_for_to_railway(
    runner: CliRunner, oauth_env: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_result, new_calls = _railway_argv(
        runner, monkeypatch, ["gmail", "--to", "railway", "--service", "api"]
    )
    old_result, old_calls = _railway_argv(
        runner, monkeypatch, ["gmail", "--deploy", "--service", "api"]
    )

    assert new_result.exit_code == 0, new_result.output
    assert old_result.exit_code == 0, old_result.output
    assert old_calls == new_calls
    assert len(new_calls) == 1
    assert new_calls[0][:3] == ["railway", "variables", "--set"]
    assert new_calls[0][3].startswith("GMAIL_OAUTH_TOKEN_JSON=")
    assert new_calls[0][4:] == ["--service", "api"]
    assert "deprecated" in old_result.stderr.lower()
    assert "--to railway" in old_result.stderr
    assert "deprecated" not in new_result.stderr.lower()
    assert "Deploy target" in new_result.output
    assert TOKEN_SENTINEL not in new_result.output
    assert TOKEN_SENTINEL not in old_result.output


def test_cli_deploy_conflicts_with_other_sink(runner: CliRunner, oauth_env: MagicMock) -> None:
    result = runner.invoke(app, ["gmail", "--deploy", "--to", "bao"])
    assert result.exit_code == 2
    assert "conflicts" in result.output
    oauth_env.from_client_secrets_file.assert_not_called()


def test_cli_service_only_applies_to_railway(runner: CliRunner, oauth_env: MagicMock) -> None:
    result = runner.invoke(app, ["gmail", "--to", "secrets-file", "--service", "api"])
    assert result.exit_code == 2
    assert "--service only applies" in result.output


def test_cli_rejects_unknown_sink(runner: CliRunner, oauth_env: MagicMock) -> None:
    result = runner.invoke(app, ["gmail", "--to", "s3"])
    assert result.exit_code == 2


def test_cli_default_is_local_only(
    runner: CliRunner, oauth_env: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.cli.auth_commands.build_sink", MagicMock(side_effect=AssertionError))
    result = runner.invoke(app, ["gmail"])
    assert result.exit_code == 0, result.output
    assert "--to railway|bao|secrets-file" in result.output


# ─── Railway allowlist (interim browser-session credentials) ───────────


def test_shipped_allowlist_includes_browser_session_credentials() -> None:
    mapping = load_mapping()
    for service in ("api", "worker"):
        names = {s.railway for s in mapping[service].secrets}
        assert {"SUBSTACK_SESSION_COOKIE", "X_AUTH_TOKEN", "X_CT0"} <= names, service
