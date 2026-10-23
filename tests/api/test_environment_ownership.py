"""Contract tests for the bounded environment-ownership status surface."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import get_settings
from src.contracts.workflow_models import EnvironmentOwnershipStatus, OwnershipDryRun

AUTHORITY_PREFIX = "d" * 12
OPERATOR_KEY = "operator-test-key-0000000000000000"


@pytest.fixture(autouse=True)
def _operator_capability(monkeypatch) -> None:
    monkeypatch.setenv("OPERATOR_API_KEY", OPERATOR_KEY)
    get_settings.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _status(*, allowed: bool | None = None) -> EnvironmentOwnershipStatus:
    dry_run = None
    if allowed is not None:
        dry_run = OwnershipDryRun(
            target_environment="gx10",
            allowed=allowed,
            next_epoch="12" if allowed else None,
            checks=(
                [
                    "shared_authority.match",
                    "current_owner.fence_first",
                    "passive_target.verify_second",
                    "target_mutations.enable_last",
                ]
                if allowed
                else ["shared_authority.mismatch"]
            ),
        )
    return EnvironmentOwnershipStatus(
        configured_environment="gx10",
        active_environment="railway",
        mode="passive" if allowed is not False else "conflict",
        authority_matches=allowed is not False,
        authority_fingerprint_prefix=AUTHORITY_PREFIX,
        epoch="11",
        passive_reasons=["environment.passive"],
        dry_run=dry_run,
    )


def test_operator_status_surface_returns_bounded_passive_identity(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.api.status_routes.environment_ownership_status",
        lambda dry_run_target=None: _status(allowed=None),
    )

    response = client.get(
        "/api/v1/status/environment-ownership",
        headers={"X-Operator-Key": OPERATOR_KEY},
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "configured_environment": "gx10",
        "active_environment": "railway",
        "mode": "passive",
        "authority_matches": True,
        "authority_fingerprint_prefix": AUTHORITY_PREFIX,
        "epoch": "11",
        "passive_reasons": ["environment.passive"],
        "dry_run": None,
    }


def test_conflicting_dry_run_returns_problem_without_mutating_ownership(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.api.status_routes.environment_ownership_status",
        lambda dry_run_target=None: _status(allowed=False),
    )

    response = client.get(
        "/api/v1/status/environment-ownership?dry_run_target=gx10",
        headers={"X-Operator-Key": OPERATOR_KEY},
    )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "environment_ownership_conflict"


def test_allowed_dry_run_reports_fence_verify_enable_order(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.api.status_routes.environment_ownership_status",
        lambda dry_run_target=None: _status(allowed=True),
    )

    response = client.get(
        "/api/v1/status/environment-ownership?dry_run_target=gx10",
        headers={"X-Operator-Key": OPERATOR_KEY},
    )

    assert response.status_code == 200
    assert response.json()["dry_run"] == {
        "target_environment": "gx10",
        "allowed": True,
        "next_epoch": "12",
        "checks": [
            "shared_authority.match",
            "current_owner.fence_first",
            "passive_target.verify_second",
            "target_mutations.enable_last",
        ],
    }


def test_operator_capability_does_not_authorize_unrelated_owner_route(client) -> None:
    response = client.get(
        "/api/v1/status/connections",
        headers={"X-Operator-Key": OPERATOR_KEY},
    )

    assert response.status_code == 401


def test_authority_unavailable_returns_bounded_problem(client, monkeypatch) -> None:
    from src.services.environment_ownership import EnvironmentOwnershipUnavailable

    def unavailable(dry_run_target=None):
        raise EnvironmentOwnershipUnavailable("postgresql://secret@example.invalid/private")

    monkeypatch.setattr(
        "src.api.status_routes.environment_ownership_status",
        unavailable,
    )

    response = client.get(
        "/api/v1/status/environment-ownership",
        headers={"X-Operator-Key": OPERATOR_KEY},
    )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "urn:aca:problem:environment-ownership-unavailable",
        "title": "Environment ownership unavailable",
        "status": 503,
        "detail": "The shared ownership authority could not be verified",
        "code": "environment_ownership_unavailable",
    }
