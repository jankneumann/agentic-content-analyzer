"""Guarded one-shot mutation release-smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.release_smoke.models import ProtectedTargetPolicy
from src.release_smoke.mutation import (
    MutationSmokeError,
    derive_idempotency_key,
    load_mutation_fixture,
    run_mutation,
)

SHA = "a" * 40
RUN_ID = "1" * 32


def _policy(target: str = "staging") -> ProtectedTargetPolicy:
    return ProtectedTargetPolicy(
        target_id=f"{target}-primary",
        target=target,
        frontend_origin=f"https://{target}-frontend.example.test",
        api_origin=f"https://{target}-api.example.test",
        expected_frontend_revision=SHA,
        expected_api_revision=SHA,
        production_origins=[
            "https://frontend.example.test",
            "https://api.example.test",
        ],
    )


def _fixture_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    fixture_root = root / "tests" / "fixtures" / "release_smoke"
    fixture_root.mkdir(parents=True)
    fixture = fixture_root / "url.json"
    fixture.write_text(
        json.dumps(
            {
                "kind": "url",
                "url": "https://example.com/release-smoke-fixture",
                "routing_mode": "webpage",
            }
        ),
        encoding="utf-8",
    )
    return root, fixture


def _operation(status: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "operation_id": "op-release-smoke",
        "operation_type": "ingestion.execute",
        "status": status,
        "progress": 100 if status == "completed" else 10,
        "message": status,
        "cancellable": status not in {"completed", "failed", "cancelled"},
        "retry_count": 0,
        "status_url": "/api/v1/operations/op-release-smoke",
        "events_url": "/api/v1/operations/op-release-smoke/events",
        "created_at": "2026-07-23T00:00:00Z",
        "completed_at": "2026-07-23T00:00:01Z" if status == "completed" else None,
    }


def test_idempotency_is_reconstructable_from_run_id() -> None:
    assert derive_idempotency_key(RUN_ID) == f"aca-release-smoke-v1:{RUN_ID}"


def test_production_mutation_is_rejected_before_fixture_or_request(tmp_path: Path) -> None:
    root, _ = _fixture_root(tmp_path)

    with pytest.raises(MutationSmokeError, match="non-production"):
        run_mutation(
            _policy("production"),
            allow_mutations=True,
            fixture_name="url.json",
            repo_root=root,
            run_id=RUN_ID,
            admin_key="admin",
        )


@pytest.mark.parametrize(
    "fixture_name",
    ["../url.json", f"{Path.cwd().anchor}outside.json"],
)
def test_fixture_must_stay_under_checked_in_root(
    tmp_path: Path,
    fixture_name: str,
) -> None:
    root, _ = _fixture_root(tmp_path)

    with pytest.raises(MutationSmokeError, match="fixture"):
        load_mutation_fixture(root, fixture_name)


def test_fixture_rejects_symlink_and_oversize(tmp_path: Path) -> None:
    root, fixture = _fixture_root(tmp_path)
    link = fixture.with_name("link.json")
    link.symlink_to(fixture)

    with pytest.raises(MutationSmokeError, match="symlink"):
        load_mutation_fixture(root, "link.json")

    fixture.write_bytes(b"x" * 65_537)
    with pytest.raises(MutationSmokeError, match="64 KiB"):
        load_mutation_fixture(root, "url.json")


def test_fixture_is_validated_as_typed_ingest_command(tmp_path: Path) -> None:
    root, fixture = _fixture_root(tmp_path)
    fixture.write_text('{"kind":"url","url":"not-a-url"}', encoding="utf-8")

    with pytest.raises(MutationSmokeError, match="IngestCommand"):
        load_mutation_fixture(root, "url.json")


def test_staging_mutation_submits_once_and_reaches_completed(tmp_path: Path) -> None:
    root, _ = _fixture_root(tmp_path)
    requests: list[httpx.Request] = []
    polls = iter(("queued", "completed"))

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(202, json=_operation("queued"))
        return httpx.Response(200, json=_operation(next(polls)))

    observation = run_mutation(
        _policy(),
        allow_mutations=True,
        fixture_name="url.json",
        repo_root=root,
        run_id=RUN_ID,
        admin_key="admin",
        transport=httpx.MockTransport(handler),
        poll_interval=0,
    )

    posts = [request for request in requests if request.method == "POST"]
    assert len(posts) == 1
    assert posts[0].url.path == "/api/v1/ingestions"
    assert posts[0].headers["Idempotency-Key"] == derive_idempotency_key(RUN_ID)
    assert observation.operation_id == "op-release-smoke"
    assert observation.status == "completed"


def test_ambiguous_submission_is_not_retried(tmp_path: Path) -> None:
    root, _ = _fixture_root(tmp_path)
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadError("response lost", request=request)

    with pytest.raises(MutationSmokeError) as captured:
        run_mutation(
            _policy(),
            allow_mutations=True,
            fixture_name="url.json",
            repo_root=root,
            run_id=RUN_ID,
            admin_key="admin",
            transport=httpx.MockTransport(handler),
        )

    assert captured.value.code == "MUTATION_AMBIGUOUS"
    assert captured.value.status == "ambiguous"
    assert attempts == 1


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_unsuccessful_terminal_state_fails(
    tmp_path: Path,
    status: str,
) -> None:
    root, _ = _fixture_root(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            202 if request.method == "POST" else 200,
            json=_operation("queued" if request.method == "POST" else status),
        )

    with pytest.raises(MutationSmokeError) as captured:
        run_mutation(
            _policy(),
            allow_mutations=True,
            fixture_name="url.json",
            repo_root=root,
            run_id=RUN_ID,
            admin_key="admin",
            transport=httpx.MockTransport(handler),
            poll_interval=0,
        )

    assert captured.value.code == f"MUTATION_{status.upper()}"
    assert captured.value.operation_id == "op-release-smoke"
