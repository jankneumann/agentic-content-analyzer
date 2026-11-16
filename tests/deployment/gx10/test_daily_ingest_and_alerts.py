"""gx-10 daily pipeline trigger, alert delivery to a person, and ingestion credentials."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from src.config.profiles import load_profile
from src.config.settings import Settings, _flatten_profile_to_settings

from .test_review_remediations import _mock_secret_tools, _read_env

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "deploy/gx10"
SYSTEMD = RUNTIME / "systemd"
DAILY = ROOT / "scripts/gx10/daily_pipeline.py"
NTFY_URL = "https://ntfy.sh/aca-gx10-alerts-k3x9q2m7"
GMAIL_TOKEN = {
    "token": "ya29.fixture",
    "refresh_token": "1//fixture-refresh",
    "client_id": "fixture.apps.googleusercontent.com",
    "client_secret": "GOCSPX-fixture",
    "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
}


def _render(tmp_path: Path, **fixtures: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    tools = _mock_secret_tools(tmp_path)
    runtime = tmp_path / "runtime"
    token = tmp_path / "token"
    token.write_text("fixture-token", encoding="utf-8")
    (tmp_path / "etc").mkdir()
    env = os.environ | {
        "PATH": f"{tools}:{os.environ['PATH']}",
        "GX10_RUNTIME_DIR": str(runtime),
        "GX10_BAO_ADDR": "http://openbao.test/v1",
        "GX10_BAO_TOKEN_FILE": str(token),
        "GX10_OPENSSL_ARGS": str(tmp_path / "openssl.args"),
        "GX10_OPENSSL_STDIN": str(tmp_path / "openssl.stdin"),
        "GX10_PUBLIC_ORIGIN": "https://gx10.example.com",
        "GX10_ALERT_PERSIST_FILE": str(tmp_path / "etc/alert.env"),
        **fixtures,
    }
    result = subprocess.run(
        [RUNTIME / "openbao/render-secrets.sh"], env=env, capture_output=True, text=True
    )
    return result, runtime


# --- Rendering ingestion credentials and the alert route ---------------------


def test_ingestion_credentials_reach_only_the_worker(tmp_path: Path) -> None:
    ingestion = {
        "gmail_oauth_token_json": json.dumps(GMAIL_TOKEN, indent=2).replace("\n", " "),
        "substack_session_cookie": "s%3Asubstack-fixture",
        "readwise_api_key": "readwise-fixture",
    }
    result, runtime = _render(tmp_path, GX10_FIXTURE_INGESTION=json.dumps(ingestion))
    assert result.returncode == 0, result.stderr

    worker = _read_env(runtime / "worker.env")
    assert json.loads(worker["GMAIL_OAUTH_TOKEN_JSON"]) == GMAIL_TOKEN
    assert " " not in worker["GMAIL_OAUTH_TOKEN_JSON"]  # compacted to one env-file token
    assert worker["SUBSTACK_SESSION_COOKIE"] == "s%3Asubstack-fixture"
    assert worker["READWISE_API_KEY"] == "readwise-fixture"
    # The root filesystem is read-only; /tmp is the worker's writable tmpfs.
    assert worker["GMAIL_TOKEN_FILE"] == "/tmp/gmail-token.json"  # noqa: S108 - container path
    for role in ("api", "scheduler", "maintenance", "common"):
        assert "GMAIL_OAUTH_TOKEN_JSON" not in _read_env(runtime / f"{role}.env")


def test_missing_optional_groups_render_with_warnings(tmp_path: Path) -> None:
    result, runtime = _render(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "no gmail_oauth_token_json" in result.stderr
    assert "alerts reach no one" in result.stderr
    assert "WORKFLOW_ALERT_SINK" not in _read_env(runtime / "common.env")
    assert (runtime / "alert.env").read_text() == ""
    assert (tmp_path / "etc/alert.env").read_text() == ""


@pytest.mark.parametrize(
    ("fixture", "value", "message"),
    [
        ("GX10_FIXTURE_INGESTION", {"gmail_password": "x"}, "not recognised"),
        (
            "GX10_FIXTURE_INGESTION",
            {"gmail_oauth_token_json": json.dumps({"token": "only-access"})},
            "refresh_token",
        ),
        ("GX10_FIXTURE_ALERTS", {"ntfy_url": "http://ntfy.sh/short"}, "ntfy_url must be"),
        ("GX10_FIXTURE_ALERTS", {"webhook": NTFY_URL}, "not recognised"),
    ],
)
def test_invalid_optional_groups_stop_the_render(
    tmp_path: Path, fixture: str, value: dict[str, str], message: str
) -> None:
    result, _ = _render(tmp_path, **{fixture: json.dumps(value)})
    assert result.returncode != 0
    assert message in result.stderr


def test_alert_route_reaches_every_app_role_and_the_host(tmp_path: Path) -> None:
    result, runtime = _render(tmp_path, GX10_FIXTURE_ALERTS=json.dumps({"ntfy_url": NTFY_URL}))
    assert result.returncode == 0, result.stderr

    common = _read_env(runtime / "common.env")
    assert common["WORKFLOW_ALERT_SINK"] == "webhook"
    assert common["WORKFLOW_ALERT_WEBHOOK_FORMAT"] == "ntfy"
    assert common["WORKFLOW_ALERT_WEBHOOK_ENDPOINT"] == NTFY_URL
    assert common["WORKFLOW_ALERT_ALLOWED_HOSTS"] == "ntfy.sh"
    assert common["WORKFLOW_ALERT_DIAGNOSTIC_ORIGIN"] == "https://gx10.example.com"
    # App containers have no direct egress: the sink goes through Squid.
    proxy = _read_env(runtime / "proxy.env")
    assert proxy["WORKFLOW_ALERT_PROXY_URL"] == proxy["HTTPS_PROXY"]
    # Host units read the persisted copy, which survives a reboot's empty /run.
    assert (runtime / "alert.env").read_text() == f"GX10_NTFY_URL={NTFY_URL}\n"
    assert (tmp_path / "etc/alert.env").read_text() == f"GX10_NTFY_URL={NTFY_URL}\n"

    # The rendered values satisfy the application's alert policy validator.
    role_environment = (
        common
        | _read_env(runtime / "worker.env")
        | proxy
        | {"GX10_PUBLIC_LANGFUSE_URL": "https://gx10.example.com/langfuse"}
    )
    profile = load_profile("gx10", profiles_dir=ROOT / "profiles", env_vars=role_environment)
    alert_settings = {
        key.lower(): value
        for key, value in role_environment.items()
        if key.startswith("WORKFLOW_ALERT_")
    }
    settings = Settings(
        _env_file=None, **(_flatten_profile_to_settings(profile.model_dump()) | alert_settings)
    )
    assert settings.workflow_alert_sink == "webhook"
    assert settings.workflow_alert_webhook_format == "ntfy"
    assert settings.workflow_alert_proxy_url is not None


def test_policy_lets_the_renderer_read_the_optional_groups() -> None:
    policy = (RUNTIME / "openbao/aca-gx10.hcl").read_text()
    assert 'path "secret/data/newsletter/gx10/ingestion"' in policy
    assert 'path "secret/data/newsletter/gx10/alerts"' in policy


# --- Host units ---------------------------------------------------------------


def test_maintenance_alert_pushes_without_the_runtime() -> None:
    unit = (SYSTEMD / "aca-gx10-maintenance-alert@.service").read_text()
    assert "EnvironmentFile=-/etc/aca/gx10/alert.env" in unit
    assert "/run/aca" not in unit.split("[Service]", 1)[1].split("ExecStart", 1)[0]
    exec_lines = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
    # The journal line first, so a failed push never loses the record.
    assert exec_lines[0].startswith("ExecStart=/usr/bin/logger")
    assert "curl" in exec_lines[1] and "$${GX10_NTFY_URL}" in exec_lines[1]
    assert "Requires=" not in unit and "After=" not in unit


def test_daily_pipeline_units_never_start_the_runtime_and_catch_up() -> None:
    service = (SYSTEMD / "aca-gx10-daily-pipeline.service").read_text()
    timer = (SYSTEMD / "aca-gx10-daily-pipeline.timer").read_text()
    assert "OnFailure=aca-gx10-maintenance-alert@%n.service" in service
    assert "ExecStartPre=/usr/bin/systemctl is-active --quiet aca-gx10.service" in service
    assert "ExecStartPre=/opt/aca/scripts/gx10/check_unit_current.sh %n" in service
    assert "Requires=" not in service
    assert "Persistent=true" in timer
    assert "[Install]" in timer and "WantedBy=timers.target" in timer


# --- Daily pipeline catch-up ---------------------------------------------------


def _load_daily():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gx10_daily_pipeline", DAILY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_days_to_run_covers_every_missed_day_up_to_yesterday() -> None:
    daily = _load_daily()
    today = date(2026, 10, 21)
    assert daily.days_to_run(None, today, 14) == [date(2026, 10, 20)]
    assert daily.days_to_run(date(2026, 10, 20), today, 14) == []
    assert daily.days_to_run(date(2026, 10, 11), today, 14) == [
        date(2026, 10, day) for day in range(12, 21)
    ]
    assert daily.days_to_run(date(2026, 9, 1), today, 3) == [
        date(2026, 10, 18),
        date(2026, 10, 19),
        date(2026, 10, 20),
    ]


def _fake_podman(tmp_path: Path, statuses: dict[str, tuple[int, str]]) -> Path:
    """A podman that records each exec and answers per period-start day."""
    log = tmp_path / "calls.jsonl"
    script = tmp_path / "podman"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"statuses = {json.dumps(statuses)}\n"
        "args = sys.argv[1:]\n"
        f"open({str(log)!r}, 'a').write(json.dumps(args) + '\\n')\n"
        "day = args[args.index('--period-start') + 1][:10]\n"
        "code, status = statuses.get(day, [0, 'completed'])\n"
        "print(json.dumps({'operation_id': '1', 'status': status}))\n"
        "sys.exit(code)\n"
    )
    script.chmod(0o700)
    return script


def _run_daily(tmp_path: Path, podman: Path, today: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(DAILY),
            "--state-file",
            str(tmp_path / "state/state.json"),
            "--podman",
            str(podman),
            "--today",
            today,
        ],
        capture_output=True,
        text=True,
    )


def _calls(tmp_path: Path) -> list[list[str]]:
    return [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]


def test_catch_up_submits_each_day_with_its_own_key_and_records_progress(tmp_path: Path) -> None:
    state = tmp_path / "state/state.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"last_completed": "2026-10-11"}))
    podman = _fake_podman(tmp_path, {})

    result = _run_daily(tmp_path, podman, "2026-10-14")

    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path)
    assert [call[call.index("--idempotency-key") + 1] for call in calls] == [
        "daily-pipeline:2026-10-12",
        "daily-pipeline:2026-10-13",
    ]
    first = calls[0]
    assert first[:2] == ["exec", "--env"]
    assert "aca-gx10_api_1" in first and "--json" in first and "--wait" in first
    assert first[first.index("--period-end") + 1] == "2026-10-13T00:00:00Z"
    assert json.loads(state.read_text()) == {"last_completed": "2026-10-13"}


@pytest.mark.parametrize("answer", [(1, "failed"), (0, "in_progress")])
def test_a_failed_or_unfinished_day_stops_and_is_retried(
    tmp_path: Path, answer: tuple[int, str]
) -> None:
    state = tmp_path / "state/state.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"last_completed": "2026-10-11"}))
    podman = _fake_podman(tmp_path, {"2026-10-12": answer})

    result = _run_daily(tmp_path, podman, "2026-10-14")

    assert result.returncode != 0
    assert len(_calls(tmp_path)) == 1  # 10-13 waits until 10-12 succeeds
    assert json.loads(state.read_text()) == {"last_completed": "2026-10-11"}
    assert "retried next run" in result.stderr


def test_first_run_does_only_yesterday(tmp_path: Path) -> None:
    podman = _fake_podman(tmp_path, {})
    result = _run_daily(tmp_path, podman, "2026-10-14")
    assert result.returncode == 0, result.stderr
    assert len(_calls(tmp_path)) == 1
    assert json.loads((tmp_path / "state/state.json").read_text()) == {
        "last_completed": "2026-10-13"
    }
