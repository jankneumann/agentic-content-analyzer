"""Read-only release-smoke policy, API, and real-process CLI tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import httpx
import pytest

from src.release_smoke.models import ProtectedTargetPolicy
from src.release_smoke.runner import (
    ReleaseSmokeError,
    build_cli_environment,
    run_api_discovery,
    run_cli_discovery,
)

SHA = "a" * 40


def _policy(**overrides: object) -> ProtectedTargetPolicy:
    values: dict[str, object] = {
        "target_id": "production-primary",
        "target": "production",
        "frontend_origin": "https://frontend.example.test",
        "api_origin": "https://api.example.test",
        "expected_frontend_revision": SHA,
        "expected_api_revision": SHA,
        "production_origins": [
            "https://frontend.example.test",
            "https://api.example.test",
        ],
    }
    values.update(overrides)
    return ProtectedTargetPolicy.model_validate(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frontend_origin", "https://user@frontend.example.test"),
        ("api_origin", "https://api.example.test/path"),
        ("api_origin", "https://api.example.test?token=no"),
        ("frontend_origin", "http://frontend.example.test"),
    ],
)
def test_non_local_policy_rejects_unsafe_origins(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        _policy(**{field: value})


def test_local_policy_allows_loopback_http_only() -> None:
    policy = _policy(
        target_id="local-fixture",
        target="local",
        frontend_origin="http://127.0.0.1:5173",
        api_origin="http://127.0.0.1:8000",
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_origins=[],
    )

    assert policy.api_origin == "http://127.0.0.1:8000"

    with pytest.raises(ValueError):
        _policy(
            target_id="local-fixture",
            target="local",
            frontend_origin="http://not-loopback.example",
            api_origin="http://127.0.0.1:8000",
            expected_frontend_revision=None,
            expected_api_revision=None,
            production_origins=[],
        )


def test_staging_policy_rejects_production_alias() -> None:
    with pytest.raises(ValueError, match="production origin"):
        _policy(
            target_id="staging-primary",
            target="staging",
            frontend_origin="https://staging.example.test",
            api_origin="https://api.example.test",
        )


def test_api_discovery_observes_revisions_and_omits_cursor() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "service": "newsletter-aggregator",
                    "revision": SHA,
                    "revision_source": "railway_commit_sha",
                },
            )
        if request.url.path == "/api/v1/capabilities":
            return httpx.Response(
                200,
                json={
                    "contract_version": "2",
                    "source_commands": [],
                    "operation_types": [],
                    "resource_types": [],
                    "next_cursor": None,
                },
            )
        if request.url.path == "/api/v1/configured-sources":
            return httpx.Response(200, json={"data": [], "next_cursor": None})
        return httpx.Response(404)

    observation = run_api_discovery(
        _policy(),
        admin_key="test-admin-key",
        transport=httpx.MockTransport(handler),
    )

    assert observation.revision == SHA
    assert observation.revision_source == "railway_commit_sha"
    discovery = requests[1:]
    assert {request.url.path for request in discovery} == {
        "/api/v1/capabilities",
        "/api/v1/configured-sources",
    }
    assert all("cursor" not in request.url.params for request in discovery)
    assert all(request.headers["X-Admin-Key"] == "test-admin-key" for request in discovery)
    assert "X-Admin-Key" not in requests[0].headers


def test_api_discovery_rejects_redirect_without_forwarding_credentials() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "revision": SHA,
                    "revision_source": "railway_commit_sha",
                },
            )
        return httpx.Response(302, headers={"Location": "https://attacker.invalid"})

    with pytest.raises(ReleaseSmokeError, match="redirect"):
        run_api_discovery(
            _policy(),
            admin_key="test-admin-key",
            transport=httpx.MockTransport(handler),
        )

    assert len(requests) == 2


def test_cli_environment_is_minimal_and_environment_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-pass")
    monkeypatch.setenv("PATH", os.environ["PATH"])

    environment = build_cli_environment(_policy(), "test-admin-key")

    assert environment["API_BASE_URL"] == "https://api.example.test"
    assert environment["ADMIN_API_KEY"] == "test-admin-key"
    assert "UNRELATED_SECRET" not in environment


def test_cli_discovery_uses_real_command_shape_and_no_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        calls.append((command, environment))
        payload = (
            {
                "contract_version": "2",
                "source_commands": [],
                "operation_types": [],
                "resource_types": [],
            }
            if command[-1] == "capabilities"
            else {"data": []}
        )
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda _executable: "/usr/local/bin/aca")

    run_cli_discovery(
        _policy(),
        admin_key="test-admin-key",
        command=("aca",),
    )

    assert [command for command, _ in calls] == [
        ["/usr/local/bin/aca", "--json", "capabilities"],
        ["/usr/local/bin/aca", "--json", "configured-sources"],
    ]
    assert all("--cursor" not in command for command, _ in calls)
    assert all("test-admin-key" not in command for command, _ in calls)
