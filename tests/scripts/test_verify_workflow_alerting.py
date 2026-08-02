from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

import scripts.verify_workflow_alerting as verifier
from scripts.verify_workflow_alerting import (
    VerificationConfig,
    VerificationError,
    validate_evidence,
    verify_workflow_alerting,
)
from tests.fixtures.workflow_alert_receiver.app import _redaction_assertions, create_app

EVENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REVISION = "a" * 40
ADMIN_KEY = "admin-secret-value"
RECEIVER_TOKEN = "receiver-secret-value"
SIGNING_SECRET = "receiver-signing-secret-at-least-32-bytes"


def _envelope() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": EVENT_ID,
        "event_key": "operation:42:claim:0:status:failed",
        "occurred_at": "2026-08-02T12:00:00Z",
        "severity": "error",
        "outcome": "failed",
        "source_kind": "operation",
        "workflow_type": "ingestion.execute",
        "release_revision": REVISION,
        "release_revision_source": "railway_commit_sha",
        "operation_id": "42",
        "attempt": 1,
        "diagnostic_url": "https://api.staging.example/api/v1/operations/42",
        "resource_refs": [],
        "source_keys": [],
        "counts": {"items_failed": 1},
        "codes": ["operation_failed"],
    }


def _config(tmp_path: Path) -> VerificationConfig:
    return VerificationConfig(
        api_origin="https://api.staging.example",
        receiver_origin="https://receiver.staging.example",
        admin_key=ADMIN_KEY,
        receiver_token=RECEIVER_TOKEN,
        expected_revision=REVISION,
        output=tmp_path / "evidence.json",
        deadline_seconds=2,
        poll_interval_seconds=0,
        production_origins=(
            "https://api.production.example",
            "https://receiver.production.example",
        ),
    )


def _receipt(*, delivery_count: int = 1) -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "event_id": EVENT_ID,
        "operation_id": "42",
        "attempt": 1,
        "outcome": "failed",
        "severity": "error",
        "release_revision": REVISION,
        "release_revision_source": "railway_commit_sha",
        "terminal_at": "2026-08-02T12:00:00Z",
        "received_at": "2026-08-02T12:00:02Z",
        "delivery_count": delivery_count,
        "redaction_assertions": {
            "no_secrets": True,
            "no_pii": True,
            "no_user_content": True,
            "no_raw_urls": True,
            "schema_valid": True,
        },
    }


def _transport(*, receipt: dict[str, object] | None = None) -> httpx.MockTransport:
    operation = {
        "schema_version": 2,
        "operation_id": "42",
        "operation_type": "ingestion.execute",
        "status": "failed",
        "progress": 100,
        "message": "Failed",
        "cancellable": False,
        "retry_count": 0,
        "status_url": "/api/v1/operations/42",
        "events_url": "/api/v1/operations/42/events",
        "resource": None,
        "result": None,
        "problem": {"type": "about:blank", "title": "Failed", "status": 500},
        "created_at": "2026-08-02T11:59:58Z",
        "started_at": "2026-08-02T11:59:59Z",
        "completed_at": "2026-08-02T12:00:00Z",
    }
    event = {
        "schema_version": 1,
        "event_id": EVENT_ID,
        "event_key": "operation:42:claim:0:status:failed",
        "source_kind": "operation",
        "operation_id": "42",
        "claim_generation": 0,
        "terminal_status": "failed",
        "classification_status": "ready",
        "release_revision": REVISION,
        "release_revision_source": "railway_commit_sha",
        "occurred_at": "2026-08-02T12:00:00Z",
        "telemetry_emitted_at": "2026-08-02T12:00:01Z",
        "delivery_counts": {
            "pending": 0,
            "leased": 0,
            "delivered": 1,
            "permanent_failure": 0,
            "exhausted": 0,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.staging.example" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy", "revision": REVISION})
        if (
            request.url.host == "api.staging.example"
            and request.url.path == "/api/v1/workflow-alert-verification-context"
        ):
            assert request.headers["X-Admin-Key"] == ADMIN_KEY
            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "environment_class": "staging",
                    "revision": REVISION,
                    "revision_source": "railway_commit_sha",
                },
            )
        if request.url.host == "receiver.staging.example" and request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "status": "ready",
                    "environment_class": "staging",
                    "single_process_required": True,
                    "signature_required": True,
                },
            )
        if request.method == "POST" and request.url.path == "/api/v1/ingestions":
            assert request.headers["X-Admin-Key"] == ADMIN_KEY
            submitted = json.loads(request.content)
            assert submitted["kind"] == "files"
            assert submitted["upload_ids"][0].startswith("upl_")
            return httpx.Response(
                202,
                json=operation,
                headers={
                    "X-Release-Revision": REVISION,
                    "X-Release-Revision-Source": "railway_commit_sha",
                },
            )
        if request.url.path == "/api/v1/operations/42":
            return httpx.Response(200, json=operation)
        if request.url.path == f"/api/v1/workflow-terminal-events/{EVENT_ID}":
            assert request.headers["X-Admin-Key"] == ADMIN_KEY
            return httpx.Response(200, json=event)
        if request.url.path == "/receipts/by-operation/42":
            assert request.headers["X-Receiver-Admin-Token"] == RECEIVER_TOKEN
            if receipt is None:
                return httpx.Response(404, json={"code": "not_found"})
            return httpx.Response(200, json=receipt)
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    return httpx.MockTransport(handler)


def test_receiver_collapses_retries_by_stable_idempotency_key() -> None:
    client = TestClient(create_app(admin_token=RECEIVER_TOKEN, signing_secret=SIGNING_SECRET))
    body = json.dumps(_envelope(), sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(SIGNING_SECRET.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "Idempotency-Key": "workflow-alert:cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "X-Workflow-Alert-Signature": f"sha256={signature}",
    }

    first = client.post("/webhook", content=body, headers=headers)
    second = client.post("/webhook", content=body, headers=headers)
    summary = client.get(
        "/receipts/by-operation/42",
        headers={"X-Receiver-Admin-Token": RECEIVER_TOKEN},
    )

    assert first.status_code == second.status_code == 202
    assert summary.status_code == 200
    assert summary.json()["delivery_count"] == 1


def test_receiver_requires_and_verifies_hmac_without_echoing_secret() -> None:
    secret = "signing-secret-that-is-long-enough"
    client = TestClient(create_app(admin_token=RECEIVER_TOKEN, signing_secret=secret))
    body = json.dumps(_envelope(), sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Idempotency-Key": "workflow-alert:cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "X-Workflow-Alert-Signature": f"sha256={signature}",
        },
    )
    rejected = client.post(
        "/webhook",
        content=body,
        headers={
            "Idempotency-Key": "workflow-alert:dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "X-Workflow-Alert-Signature": "sha256=invalid-secret-value",
        },
    )

    assert response.status_code == 202
    assert rejected.status_code == 401
    assert secret not in rejected.text
    assert "invalid-secret-value" not in rejected.text


def test_receiver_accepts_legacy_envelope_and_omits_absent_provenance() -> None:
    client = TestClient(create_app(admin_token=RECEIVER_TOKEN, signing_secret=SIGNING_SECRET))
    document = _envelope()
    document.pop("release_revision")
    document.pop("release_revision_source")
    body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(SIGNING_SECRET.encode(), body, hashlib.sha256).hexdigest()

    accepted = client.post(
        "/webhook",
        content=body,
        headers={
            "Idempotency-Key": "workflow-alert:cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "X-Workflow-Alert-Signature": f"sha256={signature}",
        },
    )
    receipt = client.get(
        "/receipts/by-operation/42",
        headers={"X-Receiver-Admin-Token": RECEIVER_TOKEN},
    )

    assert accepted.status_code == 202
    assert receipt.status_code == 200
    assert "release_revision" not in receipt.json()
    assert "release_revision_source" not in receipt.json()


@pytest.mark.parametrize("signing_secret", [None, "too-short"])
def test_receiver_without_valid_signing_secret_is_not_ready_and_rejects_delivery(
    signing_secret: str | None,
) -> None:
    client = TestClient(create_app(admin_token=RECEIVER_TOKEN, signing_secret=signing_secret))
    body = json.dumps(_envelope(), sort_keys=True, separators=(",", ":")).encode()

    health = client.get("/health")
    response = client.post(
        "/webhook",
        content=body,
        headers={"Idempotency-Key": "workflow-alert:cccccccc-cccc-4ccc-8ccc-cccccccccccc"},
    )

    assert health.json()["status"] == "not_ready"
    assert health.json()["signature_required"] is True
    assert response.status_code == 503


def test_receiver_rejects_unknown_or_oversized_bodies_with_safe_errors() -> None:
    client = TestClient(
        create_app(
            admin_token=RECEIVER_TOKEN,
            signing_secret=SIGNING_SECRET,
            max_body_bytes=1024,
        )
    )
    hostile = _envelope() | {"raw_error": "sk-secret user@example.com"}
    hostile_body = json.dumps(hostile).encode()
    hostile_signature = hmac.new(SIGNING_SECRET.encode(), hostile_body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=hostile_body,
        headers={
            "Idempotency-Key": "workflow-alert:cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "X-Workflow-Alert-Signature": f"sha256={hostile_signature}",
        },
    )
    oversized = client.post(
        "/webhook",
        content=b"x" * 1025,
        headers={"Idempotency-Key": "workflow-alert:cccccccc-cccc-4ccc-8ccc-cccccccccccc"},
    )

    assert response.status_code == 422
    assert oversized.status_code == 413
    assert "sk-secret" not in response.text
    assert "user@example.com" not in response.text


def test_receiver_redaction_scan_detects_nested_raw_url() -> None:
    hostile = _envelope()
    hostile["resource_refs"] = [{"type": "content", "id": "https://raw.example/item"}]

    assertions = _redaction_assertions(hostile)

    assert assertions["no_raw_urls"] is False


def test_verifier_correlates_receipt_hash_and_writes_schema_valid_evidence(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    with httpx.Client(transport=_transport(receipt=_receipt())) as client:
        evidence = verify_workflow_alerting(config, client=client)

    assert validate_evidence(evidence) == []
    assert evidence["revision"] == REVISION
    assert evidence["revision_source"] == "railway_commit_sha"
    assert (
        evidence["receipt_sha256"]
        == hashlib.sha256(UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb").bytes).hexdigest()
    )
    assert json.loads(config.output.read_text()) == evidence
    serialized = config.output.read_text()
    assert "staging.example" not in serialized
    assert ADMIN_KEY not in serialized
    assert RECEIVER_TOKEN not in serialized


def test_verifier_fails_closed_when_receipt_is_missing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with httpx.Client(transport=_transport(receipt=None)) as client:
        with pytest.raises(VerificationError, match="deadline_exceeded"):
            verify_workflow_alerting(config, client=client)
    assert not config.output.exists()


def test_verifier_removes_prior_valid_evidence_before_failed_run(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with httpx.Client(transport=_transport(receipt=_receipt())) as client:
        verify_workflow_alerting(config, client=client)

    with httpx.Client(transport=_transport(receipt=None)) as client:
        with pytest.raises(VerificationError, match="deadline_exceeded"):
            verify_workflow_alerting(config, client=client)

    assert not config.output.exists()


def test_verifier_preserves_unowned_existing_output_and_symlink(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.output.write_text('{"unrelated":"document"}')

    with pytest.raises(VerificationError, match="output_ownership_unknown"):
        verify_workflow_alerting(config)
    assert config.output.read_text() == '{"unrelated":"document"}'

    config.output.unlink()
    target = tmp_path / "unrelated-target.json"
    target.write_text('{"important":true}')
    config.output.symlink_to(target)
    with pytest.raises(VerificationError, match="output_ownership_unknown"):
        verify_workflow_alerting(config)
    assert config.output.is_symlink()
    assert target.read_text() == '{"important":true}'


def test_verifier_preserves_unowned_legacy_temporary_file(tmp_path: Path) -> None:
    config = _config(tmp_path)
    legacy_temporary = config.output.with_suffix(config.output.suffix + ".tmp")
    legacy_temporary.write_text("unrelated temporary document")

    with pytest.raises(VerificationError, match="output_ownership_unknown"):
        verify_workflow_alerting(config)

    assert legacy_temporary.read_text() == "unrelated temporary document"
    assert not config.output.exists()


def test_verifier_closes_output_cleanup_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    with httpx.Client(transport=_transport(receipt=_receipt())) as client:
        verify_workflow_alerting(config, client=client)

    def denied(*args, **kwargs) -> None:
        raise PermissionError("/secret/output/path")

    monkeypatch.setattr(Path, "unlink", denied)
    with pytest.raises(VerificationError) as caught:
        verify_workflow_alerting(config)
    assert str(caught.value) == "output_cleanup_failed"
    assert "secret" not in str(caught.value)


def test_verifier_rejects_duplicate_receiver_notification(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with httpx.Client(transport=_transport(receipt=_receipt(delivery_count=2))) as client:
        with pytest.raises(VerificationError, match="duplicate_receipt"):
            verify_workflow_alerting(config, client=client)
    assert not config.output.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outcome", "partial"),
        ("severity", "warning"),
        ("terminal_at", "2026-08-02T11:59:59Z"),
    ],
)
def test_verifier_rejects_receipt_classification_or_timestamp_mismatch(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    mismatched_receipt = _receipt()
    mismatched_receipt[field] = value
    with httpx.Client(transport=_transport(receipt=mismatched_receipt)) as client:
        with pytest.raises(VerificationError, match="correlation_failed"):
            verify_workflow_alerting(_config(tmp_path), client=client)


def test_evidence_validator_rejects_schema_and_redaction_failures(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with httpx.Client(transport=_transport(receipt=_receipt())) as client:
        evidence = verify_workflow_alerting(config, client=client)
    evidence["unexpected"] = "raw body"
    evidence["redaction_assertions"]["no_secrets"] = False

    errors = validate_evidence(evidence)

    assert errors
    assert all("raw body" not in error for error in errors)


def test_config_rejects_non_staging_and_production_or_unsafe_origins(tmp_path: Path) -> None:
    with pytest.raises(VerificationError, match="unsafe_origin"):
        VerificationConfig(
            api_origin="http://api.staging.example",
            receiver_origin="https://receiver.staging.example",
            production_origins=("https://api.production.example",),
            admin_key=ADMIN_KEY,
            receiver_token=RECEIVER_TOKEN,
            expected_revision=REVISION,
            output=tmp_path / "evidence.json",
        )
    with pytest.raises(VerificationError, match="production_target_rejected"):
        VerificationConfig(
            api_origin="https://api.staging.example",
            receiver_origin="https://receiver.staging.example",
            production_origins=("https://api.staging.example",),
            admin_key=ADMIN_KEY,
            receiver_token=RECEIVER_TOKEN,
            expected_revision=REVISION,
            output=tmp_path / "evidence.json",
        )
    with pytest.raises(VerificationError, match="production_target_rejected"):
        VerificationConfig(
            api_origin="https://[2001:db8::1]:443",
            receiver_origin="https://receiver.staging.example",
            production_origins=("https://[2001:db8::1]",),
            admin_key=ADMIN_KEY,
            receiver_token=RECEIVER_TOKEN,
            expected_revision=REVISION,
            output=tmp_path / "evidence.json",
        )
    with pytest.raises(VerificationError, match="production_denylist_missing"):
        VerificationConfig(
            api_origin="https://api.staging.example",
            receiver_origin="https://receiver.staging.example",
            admin_key=ADMIN_KEY,
            receiver_token=RECEIVER_TOKEN,
            expected_revision=REVISION,
            output=tmp_path / "evidence.json",
        )
    with pytest.raises(VerificationError, match="production_target_rejected"):
        VerificationConfig(
            api_origin="https://api.production.example:443",
            receiver_origin="https://receiver.staging.example",
            production_origins=("https://api.production.example",),
            admin_key=ADMIN_KEY,
            receiver_token=RECEIVER_TOKEN,
            expected_revision=REVISION,
            output=tmp_path / "evidence.json",
        )


def test_verifier_converts_transport_errors_to_safe_closed_code(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("https://user:password@secret.example/body=raw")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VerificationError) as caught:
            verify_workflow_alerting(_config(tmp_path), client=client)

    assert str(caught.value) == "transport_error"
    assert "secret.example" not in str(caught.value)


def test_verifier_streams_and_caps_response_before_json_decode(tmp_path: Path) -> None:
    class OversizedStream(httpx.SyncByteStream):
        chunks_read = 0

        def __iter__(self):
            for chunk in (b"x" * 40_000, b"x" * 40_000, b"never-read"):
                self.chunks_read += 1
                yield chunk

    stream = OversizedStream()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept-Encoding"] == "identity"
        return httpx.Response(200, stream=stream)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VerificationError, match="response_too_large"):
            verify_workflow_alerting(_config(tmp_path), client=client)
    assert stream.chunks_read == 2


def test_verifier_removes_partial_artifacts_when_final_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)

    def denied_replace(self: Path, target: Path) -> None:
        raise PermissionError("/secret/output/path")

    monkeypatch.setattr(Path, "replace", denied_replace)
    with httpx.Client(transport=_transport(receipt=_receipt())) as client:
        with pytest.raises(VerificationError) as caught:
            verify_workflow_alerting(config, client=client)

    assert str(caught.value) == "output_write_failed"
    assert not config.output.exists()
    assert list(tmp_path.glob(".*.workflow-alert-*.tmp")) == []


def test_verifier_requires_positive_staging_context_before_submission(tmp_path: Path) -> None:
    submissions = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal submissions
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy", "revision": REVISION})
        if request.url.path == "/api/v1/workflow-alert-verification-context":
            return httpx.Response(503, json={"code": "unavailable"})
        if request.method == "POST":
            submissions += 1
        return httpx.Response(500, json={"code": "unexpected"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VerificationError, match="verification_context_unavailable"):
            verify_workflow_alerting(_config(tmp_path), client=client)
    assert submissions == 0


def test_verifier_rechecks_staging_context_after_correlation(tmp_path: Path) -> None:
    context_reads = 0
    base_transport = _transport(receipt=_receipt())

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal context_reads
        if request.url.path == "/api/v1/workflow-alert-verification-context":
            context_reads += 1
            revision = REVISION if context_reads == 1 else "b" * 40
            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "environment_class": "staging",
                    "revision": revision,
                    "revision_source": "railway_commit_sha",
                },
            )
        return base_transport.handle_request(request)

    config = _config(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VerificationError, match="verification_context_mismatch"):
            verify_workflow_alerting(config, client=client)
    assert context_reads == 2
    assert not config.output.exists()


@pytest.mark.parametrize(
    ("surface", "field", "value"),
    [
        ("submit", "X-Release-Revision-Source", None),
        ("submit", "X-Release-Revision", "b" * 40),
        ("event", "release_revision", "b" * 40),
        ("receipt", "release_revision_source", "unavailable"),
    ],
)
def test_verifier_rejects_mixed_or_untrusted_release_provenance(
    tmp_path: Path,
    surface: str,
    field: str,
    value: str | None,
) -> None:
    base_transport = _transport(receipt=_receipt())

    def handler(request: httpx.Request) -> httpx.Response:
        response = base_transport.handle_request(request)
        if surface == "submit" and request.method == "POST":
            if value is None:
                del response.headers[field]
            else:
                response.headers[field] = value
        elif (
            surface == "event" and request.url.path.startswith("/api/v1/workflow-terminal-events/")
        ) or (surface == "receipt" and request.url.path.startswith("/receipts/by-operation/")):
            document = response.json()
            if value is None:
                document.pop(field, None)
            else:
                document[field] = value
            response = httpx.Response(200, json=document)
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VerificationError, match="release_provenance_mismatch"):
            verify_workflow_alerting(_config(tmp_path), client=client)


def test_cli_converts_unexpected_errors_to_safe_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    values = {
        "WORKFLOW_ALERT_VERIFY_TARGET_CLASS": "staging",
        "WORKFLOW_ALERT_VERIFY_API_ORIGIN": "https://api.staging.example",
        "WORKFLOW_ALERT_VERIFY_RECEIVER_ORIGIN": "https://receiver.staging.example",
        "WORKFLOW_ALERT_VERIFY_EXPECTED_REVISION": REVISION,
        "WORKFLOW_ALERT_VERIFY_PRODUCTION_ORIGINS": "https://api.production.example",
        "ADMIN_API_KEY": ADMIN_KEY,
        "WORKFLOW_ALERT_RECEIVER_ADMIN_TOKEN": RECEIVER_TOKEN,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        verifier,
        "verify_workflow_alerting",
        lambda config: (_ for _ in ()).throw(
            RuntimeError("https://user:password@secret.example/raw-body")
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["verify_workflow_alerting.py", "--output", str(tmp_path / "evidence.json")],
    )

    assert verifier.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "workflow alert staging verification: FAILED (unexpected_error)\n"
