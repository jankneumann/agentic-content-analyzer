#!/usr/bin/env python3
"""Create and verify one sanitized workflow alert in non-production staging."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SCHEMA = (
    REPO_ROOT / "openspec/changes/production-telemetry-and-out-of-band-alerting/contracts/"
    "staging-evidence.schema.json"
)
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_POSITIVE_ID = re.compile(r"^[1-9][0-9]{0,18}$")
_RECEIPT_BASE_KEYS = {
    "schema_version",
    "receipt_id",
    "event_id",
    "operation_id",
    "attempt",
    "outcome",
    "severity",
    "terminal_at",
    "received_at",
    "delivery_count",
    "redaction_assertions",
}
_RECEIPT_PROVENANCE_KEYS = {"release_revision", "release_revision_source"}
_ASSERTION_KEYS = {"no_secrets", "no_pii", "no_user_content", "no_raw_urls", "schema_valid"}
_MAX_RESPONSE_BYTES = 65_536
_CONTEXT_KEYS = {"schema_version", "environment_class", "revision", "revision_source"}


class VerificationError(RuntimeError):
    """Closed verifier failure whose message is safe for logs and CI output."""


def _normalized_https_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise VerificationError("unsafe_origin") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise VerificationError("unsafe_origin")
    host = parsed.hostname.lower().rstrip(".")
    if not host:
        raise VerificationError("unsafe_origin")
    authority_host = f"[{host}]" if ":" in host else host
    authority = f"{authority_host}:{port}" if port is not None and port != 443 else authority_host
    return f"https://{authority}"


@dataclass(frozen=True, slots=True)
class VerificationConfig:
    api_origin: str
    receiver_origin: str
    admin_key: str
    receiver_token: str
    expected_revision: str
    output: Path
    deadline_seconds: int = 180
    poll_interval_seconds: float = 2.0
    production_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        api_origin = _normalized_https_origin(self.api_origin)
        receiver_origin = _normalized_https_origin(self.receiver_origin)
        production_origins = tuple(
            _normalized_https_origin(origin) for origin in self.production_origins
        )
        if not production_origins:
            raise VerificationError("production_denylist_missing")
        if api_origin in production_origins or receiver_origin in production_origins:
            raise VerificationError("production_target_rejected")
        if not self.admin_key or not self.receiver_token:
            raise VerificationError("missing_credentials")
        if _COMMIT_SHA.fullmatch(self.expected_revision) is None:
            raise VerificationError("invalid_revision")
        if not 1 <= self.deadline_seconds <= 900:
            raise VerificationError("invalid_deadline")
        if not 0 <= self.poll_interval_seconds <= 30:
            raise VerificationError("invalid_poll_interval")
        object.__setattr__(self, "api_origin", api_origin)
        object.__setattr__(self, "receiver_origin", receiver_origin)
        object.__setattr__(self, "production_origins", production_origins)


@dataclass(frozen=True, slots=True)
class _BoundedResponse:
    status_code: int
    document: dict[str, Any]
    release_revision: str | None
    release_revision_source: str | None


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> _BoundedResponse:
    try:
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("Accept-Encoding", "identity")
        with client.stream(
            method,
            url,
            headers=headers,
            follow_redirects=False,
            **kwargs,
        ) as response:
            declared_length = response.headers.get("content-length")
            if declared_length is not None:
                try:
                    if int(declared_length) > _MAX_RESPONSE_BYTES:
                        raise VerificationError("response_too_large")
                except ValueError as exc:
                    raise VerificationError("invalid_response") from exc
            # HTTPX marks explicitly materialized responses (including
            # MockTransport fixtures) as consumed before the client sees them.
            # Real network responses take the streaming branch, so their body is
            # capped before it can be buffered by this verifier.
            body = bytearray(response.content) if response.is_stream_consumed else bytearray()
            if len(body) > _MAX_RESPONSE_BYTES:
                raise VerificationError("response_too_large")
            if not response.is_stream_consumed:
                for chunk in response.iter_raw():
                    if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                        raise VerificationError("response_too_large")
                    body.extend(chunk)
            try:
                value = json.loads(body)
            except (UnicodeDecodeError, ValueError) as exc:
                raise VerificationError("invalid_response") from exc
            if not isinstance(value, dict):
                raise VerificationError("invalid_response")
            return _BoundedResponse(
                status_code=response.status_code,
                document=value,
                release_revision=response.headers.get("X-Release-Revision"),
                release_revision_source=response.headers.get("X-Release-Revision-Source"),
            )
    except httpx.HTTPError as exc:
        raise VerificationError("transport_error") from exc


def _clear_previous_output(config: VerificationConfig) -> None:
    try:
        legacy_temporary = config.output.with_suffix(config.output.suffix + ".tmp")
        if legacy_temporary.is_symlink() or legacy_temporary.exists():
            raise VerificationError("output_ownership_unknown")
        if config.output.is_symlink():
            raise VerificationError("output_ownership_unknown")
        if not config.output.exists():
            return
        if not config.output.is_file() or config.output.stat().st_size > _MAX_RESPONSE_BYTES:
            raise VerificationError("output_ownership_unknown")
        try:
            document = json.loads(config.output.read_bytes())
        except (UnicodeDecodeError, ValueError):
            raise VerificationError("output_ownership_unknown") from None
        if validate_evidence(document):
            raise VerificationError("output_ownership_unknown")
        config.output.unlink()
    except VerificationError:
        raise
    except OSError as exc:
        raise VerificationError("output_cleanup_failed") from exc


def _require_release_provenance(config: VerificationConfig, document: dict[str, Any]) -> None:
    if (
        document.get("release_revision") != config.expected_revision
        or document.get("release_revision_source") != "railway_commit_sha"
    ):
        raise VerificationError("release_provenance_mismatch")


def _verified_staging_revision(
    config: VerificationConfig,
    client: httpx.Client,
) -> str:
    response = _request(
        client,
        "GET",
        f"{config.api_origin}/api/v1/workflow-alert-verification-context",
        headers={"X-Admin-Key": config.admin_key},
    )
    if response.status_code != 200:
        raise VerificationError("verification_context_unavailable")
    context = response.document
    revision = context.get("revision")
    if not isinstance(revision, str):
        raise VerificationError("verification_context_mismatch")
    if (
        set(context) != _CONTEXT_KEYS
        or context.get("schema_version") != 1
        or context.get("environment_class") != "staging"
        or context.get("revision_source") != "railway_commit_sha"
        or revision != config.expected_revision
        or _COMMIT_SHA.fullmatch(revision) is None
    ):
        raise VerificationError("verification_context_mismatch")
    return revision


def validate_evidence(document: object) -> list[str]:
    """Return location-only schema errors without reflecting evidence values."""

    try:
        schema = json.loads(EVIDENCE_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VerificationError("evidence_schema_unavailable") from exc
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    return [
        "<root>" if not error.absolute_path else ".".join(map(str, error.absolute_path))
        for error in errors
    ]


def _controlled_upload_id() -> str:
    marker = f"uploads/ri09_verify_{uuid4().hex}_user_content.upload.json"
    return "upl_" + base64.urlsafe_b64encode(marker.encode()).decode().rstrip("=")


def _validate_receipt(receipt: dict[str, Any], operation_id: str) -> None:
    keys = set(receipt)
    if (
        keys not in (_RECEIPT_BASE_KEYS, _RECEIPT_BASE_KEYS | _RECEIPT_PROVENANCE_KEYS)
        or receipt.get("schema_version") != 1
    ):
        raise VerificationError("invalid_receipt")
    assertions = receipt.get("redaction_assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != _ASSERTION_KEYS
        or not all(assertions.get(key) is True for key in _ASSERTION_KEYS)
    ):
        raise VerificationError("redaction_failed")
    if receipt.get("operation_id") != operation_id:
        raise VerificationError("correlation_failed")
    if receipt.get("delivery_count") != 1:
        raise VerificationError("duplicate_receipt")
    try:
        UUID(str(receipt["receipt_id"]))
        UUID(str(receipt["event_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise VerificationError("invalid_receipt") from exc


def _poll(
    config: VerificationConfig,
    client: httpx.Client,
    operation_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + config.deadline_seconds
    headers = {"X-Admin-Key": config.admin_key}
    receiver_headers = {"X-Receiver-Admin-Token": config.receiver_token}
    while True:
        operation_response = _request(
            client,
            "GET",
            f"{config.api_origin}/api/v1/operations/{operation_id}",
            headers=headers,
        )
        if operation_response.status_code != 200:
            raise VerificationError("operation_read_failed")
        operation = operation_response.document
        receipt_response = _request(
            client,
            "GET",
            f"{config.receiver_origin}/receipts/by-operation/{operation_id}",
            headers=receiver_headers,
        )
        if operation.get("status") == "failed" and receipt_response.status_code == 200:
            return operation, receipt_response.document
        if operation.get("status") in {"completed", "cancelled"}:
            raise VerificationError("controlled_outcome_mismatch")
        if receipt_response.status_code not in {200, 404}:
            raise VerificationError("receiver_read_failed")
        if config.poll_interval_seconds == 0 or time.monotonic() >= deadline:
            raise VerificationError("deadline_exceeded")
        time.sleep(min(config.poll_interval_seconds, max(0, deadline - time.monotonic())))


def verify_workflow_alerting(
    config: VerificationConfig,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Exercise one controlled failed operation and persist only sanitized proof."""

    _clear_previous_output(config)
    owns_client = client is None
    active_client = client or httpx.Client(timeout=httpx.Timeout(10), trust_env=False)
    try:
        health_response = _request(active_client, "GET", f"{config.api_origin}/health")
        if health_response.status_code != 200:
            raise VerificationError("health_check_failed")
        health = health_response.document
        if health.get("revision") != config.expected_revision:
            raise VerificationError("revision_mismatch")
        verified_revision = _verified_staging_revision(config, active_client)
        receiver_health_response = _request(
            active_client, "GET", f"{config.receiver_origin}/health"
        )
        if receiver_health_response.status_code != 200:
            raise VerificationError("receiver_health_check_failed")
        receiver_health = receiver_health_response.document
        if (
            receiver_health.get("status") != "ready"
            or receiver_health.get("environment_class") != "staging"
            or receiver_health.get("single_process_required") is not True
            or receiver_health.get("signature_required") is not True
        ):
            raise VerificationError("receiver_not_ready")

        submit_response = _request(
            active_client,
            "POST",
            f"{config.api_origin}/api/v1/ingestions",
            headers={
                "X-Admin-Key": config.admin_key,
                "Idempotency-Key": f"ri09-staging-{uuid4()}",
            },
            json={"kind": "files", "upload_ids": [_controlled_upload_id()]},
        )
        if submit_response.status_code != 202:
            raise VerificationError("controlled_submit_failed")
        if (
            submit_response.release_revision != verified_revision
            or submit_response.release_revision_source != "railway_commit_sha"
        ):
            raise VerificationError("release_provenance_mismatch")
        submitted = submit_response.document
        operation_id = str(submitted.get("operation_id", ""))
        if _POSITIVE_ID.fullmatch(operation_id) is None:
            raise VerificationError("invalid_operation_identity")

        operation, receipt = _poll(config, active_client, operation_id)
        _validate_receipt(receipt, operation_id)
        _require_release_provenance(config, receipt)
        event_id = str(receipt["event_id"])
        event_response = _request(
            active_client,
            "GET",
            f"{config.api_origin}/api/v1/workflow-terminal-events/{event_id}",
            headers={"X-Admin-Key": config.admin_key},
        )
        if event_response.status_code != 200:
            raise VerificationError("event_read_failed")
        event = event_response.document
        _require_release_provenance(config, event)
        counts = event.get("delivery_counts")
        expected_attempt = (
            event.get("claim_generation", -1) + 1
            if isinstance(event.get("claim_generation"), int)
            else None
        )
        try:
            terminal_at = datetime.fromisoformat(str(event.get("occurred_at", "")))
            receipt_terminal_at = datetime.fromisoformat(str(receipt.get("terminal_at", "")))
            received_at = datetime.fromisoformat(str(receipt.get("received_at", "")))
            timestamps_correlate = (
                terminal_at.tzinfo is not None
                and receipt_terminal_at.tzinfo is not None
                and received_at.tzinfo is not None
                and terminal_at == receipt_terminal_at
                and received_at >= terminal_at
            )
        except ValueError:
            timestamps_correlate = False
        if (
            event.get("event_id") != event_id
            or event.get("operation_id") != operation_id
            or event.get("terminal_status") != "failed"
            or event.get("classification_status") != "ready"
            or event.get("telemetry_emitted_at") is None
            or expected_attempt != receipt.get("attempt")
            or receipt.get("outcome") != "failed"
            or receipt.get("severity") != "error"
            or not timestamps_correlate
            or not isinstance(counts, dict)
            or counts.get("delivered") != 1
            or any(
                counts.get(key) != 0
                for key in ("pending", "leased", "permanent_failure", "exhausted")
            )
            or operation.get("operation_id") != operation_id
            or operation.get("status") != "failed"
        ):
            raise VerificationError("correlation_failed")

        if _verified_staging_revision(config, active_client) != verified_revision:
            raise VerificationError("verification_context_changed")

        receipt_id = UUID(str(receipt["receipt_id"]))
        evidence = {
            "schema_version": 1,
            "environment_class": "staging",
            "revision": verified_revision,
            "revision_source": "railway_commit_sha",
            "operation_id": operation_id,
            "attempt": receipt["attempt"],
            "event_id": event_id,
            "outcome": receipt["outcome"],
            "severity": receipt["severity"],
            "terminal_at": event["occurred_at"],
            "received_at": receipt["received_at"],
            "receipt_sha256": hashlib.sha256(receipt_id.bytes).hexdigest(),
            "delivery_count": 1,
            "redaction_assertions": receipt["redaction_assertions"],
        }
        if validate_evidence(evidence):
            raise VerificationError("evidence_schema_invalid")
        temporary: Path | None = None
        try:
            config.output.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=config.output.parent,
                prefix=f".{config.output.name}.workflow-alert-",
                suffix=".tmp",
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(config.output)
        except OSError as exc:
            try:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                config.output.unlink(missing_ok=True)
            except OSError:
                pass
            raise VerificationError("output_write_failed") from exc
        return evidence
    finally:
        if owns_client:
            active_client.close()


def _config_from_environment(args: argparse.Namespace) -> VerificationConfig:
    api_origin = os.getenv("WORKFLOW_ALERT_VERIFY_API_ORIGIN")
    receiver_origin = os.getenv("WORKFLOW_ALERT_VERIFY_RECEIVER_ORIGIN")
    admin_key = os.getenv("ADMIN_API_KEY")
    receiver_token = os.getenv("WORKFLOW_ALERT_RECEIVER_ADMIN_TOKEN")
    expected_revision = os.getenv("WORKFLOW_ALERT_VERIFY_EXPECTED_REVISION")
    if os.getenv("WORKFLOW_ALERT_VERIFY_TARGET_CLASS") != "staging" or any(
        value is None
        for value in (api_origin, receiver_origin, admin_key, receiver_token, expected_revision)
    ):
        raise VerificationError("staging_configuration_missing")
    assert api_origin is not None
    assert receiver_origin is not None
    assert admin_key is not None
    assert receiver_token is not None
    assert expected_revision is not None
    raw_production_origins = os.getenv("WORKFLOW_ALERT_VERIFY_PRODUCTION_ORIGINS")
    if raw_production_origins is None:
        raise VerificationError("production_denylist_missing")
    production_origins = tuple(
        item.strip() for item in raw_production_origins.split(",") if item.strip()
    )
    return VerificationConfig(
        api_origin=api_origin,
        receiver_origin=receiver_origin,
        admin_key=admin_key,
        receiver_token=receiver_token,
        expected_revision=expected_revision,
        output=args.output,
        deadline_seconds=args.deadline_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        production_origins=production_origins,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline-seconds", type=int, default=180)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    args = parser.parse_args()
    try:
        config = _config_from_environment(args)
        verify_workflow_alerting(config)
    except VerificationError as exc:
        print(f"workflow alert staging verification: FAILED ({exc})", file=sys.stderr)
        return 1
    except Exception:
        print("workflow alert staging verification: FAILED (unexpected_error)", file=sys.stderr)
        return 1
    print("workflow alert staging verification: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
