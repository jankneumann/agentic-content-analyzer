"""Single-process, non-production receiver for workflow-alert staging proof.

The fixture retains only a closed receipt summary. It never exposes or stores
the webhook body, headers, endpoint, signing material, or arbitrary errors.
Run exactly one process: the in-memory idempotency registry is intentionally
bounded to a verification deployment, not a production notification service.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.contracts.workflow_alert_models import WorkflowAlertEnvelopeV1

_DELIVERY_KEY = re.compile(
    r"^workflow-alert:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET_MARKERS = ("sk-", "api_key", "authorization", "password", "secret", "token=")
_USER_CONTENT_MARKERS = (
    "raw_error",
    "error_message",
    "problem_detail",
    "markdown_content",
    "user_content",
    "ri09_verify_",
)


@dataclass(frozen=True, slots=True)
class _Receipt:
    receipt_id: str
    event_id: str
    operation_id: str
    attempt: int
    outcome: str
    severity: str
    release_revision: str | None
    release_revision_source: str | None
    terminal_at: str
    received_at: str
    body_sha256: str
    redaction_assertions: dict[str, bool]


def _safe_error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code})


def _string_values(value: object, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    if isinstance(value, dict):
        return [
            item
            for key, child in value.items()
            for item in _string_values(child, (*path, str(key)))
        ]
    if isinstance(value, list):
        return [
            item
            for index, child in enumerate(value)
            for item in _string_values(child, (*path, str(index)))
        ]
    return [(path, value)] if isinstance(value, str) else []


def _redaction_assertions(document: dict[str, Any]) -> dict[str, bool]:
    serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
    lowered = serialized.lower()
    url_values = [
        (path, value)
        for path, value in _string_values(document)
        if value.startswith(("http://", "https://"))
    ]
    return {
        "no_secrets": not any(marker in lowered for marker in _SECRET_MARKERS),
        "no_pii": _EMAIL.search(serialized) is None,
        "no_user_content": not any(marker in lowered for marker in _USER_CONTENT_MARKERS),
        "no_raw_urls": len(url_values) == 1
        and url_values[0] == (("diagnostic_url",), document.get("diagnostic_url")),
        "schema_valid": True,
    }


def create_app(
    *,
    admin_token: str | None = None,
    signing_secret: str | None = None,
    max_body_bytes: int = 32_768,
    max_receipts: int = 1000,
) -> FastAPI:
    """Create a bounded receiver; secrets default to environment-only values."""

    configured_admin_token = admin_token or os.getenv("WORKFLOW_ALERT_RECEIVER_ADMIN_TOKEN")
    configured_signing_secret = signing_secret or os.getenv("WORKFLOW_ALERT_WEBHOOK_SECRET")
    signature_configured = bool(configured_signing_secret and len(configured_signing_secret) >= 32)
    if not 1024 <= max_body_bytes <= 65_536:
        raise ValueError("max_body_bytes is outside the fixture range")
    if not 1 <= max_receipts <= 10_000:
        raise ValueError("max_receipts is outside the fixture range")

    app = FastAPI(title="Workflow Alert Staging Receiver", docs_url=None, redoc_url=None)
    lock = Lock()
    receipts_by_key: dict[str, _Receipt] = {}

    def authorized(request: Request) -> bool:
        supplied = request.headers.get("X-Receiver-Admin-Token", "")
        return bool(
            configured_admin_token
            and supplied
            and hmac.compare_digest(supplied, configured_admin_token)
        )

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": ("ready" if configured_admin_token and signature_configured else "not_ready"),
            "environment_class": "staging",
            "single_process_required": True,
            "signature_required": True,
        }

    @app.post("/webhook")
    async def receive(request: Request) -> JSONResponse:
        if not signature_configured or configured_signing_secret is None:
            return _safe_error(503, "receiver_not_ready")
        declared_length = request.headers.get("content-length")
        if declared_length is not None:
            try:
                if int(declared_length) > max_body_bytes:
                    return _safe_error(413, "body_too_large")
            except ValueError:
                return _safe_error(400, "invalid_request")
        received = 0
        chunks: list[bytes] = []
        async for chunk in request.stream():
            received += len(chunk)
            if received > max_body_bytes:
                return _safe_error(413, "body_too_large")
            chunks.append(chunk)
        body = b"".join(chunks)

        delivery_key = request.headers.get("Idempotency-Key", "")
        if _DELIVERY_KEY.fullmatch(delivery_key) is None:
            return _safe_error(400, "invalid_delivery_key")
        supplied_signature = request.headers.get("X-Workflow-Alert-Signature", "")
        expected_signature = (
            "sha256="
            + hmac.new(configured_signing_secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return _safe_error(401, "invalid_signature")

        try:
            raw_document = json.loads(body)
            if not isinstance(raw_document, dict):
                raise ValueError
            envelope = WorkflowAlertEnvelopeV1.model_validate(raw_document)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError):
            return _safe_error(422, "invalid_envelope")

        body_sha256 = hashlib.sha256(body).hexdigest()
        with lock:
            previous = receipts_by_key.get(delivery_key)
            if previous is not None:
                if previous.body_sha256 != body_sha256:
                    return _safe_error(409, "idempotency_conflict")
                return JSONResponse(status_code=202, content={"status": "accepted"})
            if len(receipts_by_key) >= max_receipts:
                return _safe_error(503, "receipt_capacity_reached")
            serialized = envelope.model_dump(mode="json")
            receipts_by_key[delivery_key] = _Receipt(
                receipt_id=str(uuid4()),
                event_id=str(envelope.event_id),
                operation_id=envelope.operation_id or "",
                attempt=envelope.attempt,
                outcome=envelope.outcome,
                severity=envelope.severity,
                release_revision=envelope.release_revision,
                release_revision_source=envelope.release_revision_source,
                terminal_at=serialized["occurred_at"],
                received_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                body_sha256=body_sha256,
                redaction_assertions=_redaction_assertions(raw_document),
            )
        return JSONResponse(status_code=202, content={"status": "accepted"})

    @app.get("/receipts/by-operation/{operation_id}")
    async def receipt_by_operation(operation_id: str, request: Request) -> JSONResponse:
        if not authorized(request):
            return _safe_error(401, "unauthorized")
        if not operation_id.isascii() or not operation_id.isdigit() or operation_id.startswith("0"):
            return _safe_error(404, "not_found")
        with lock:
            matches = [
                receipt
                for receipt in receipts_by_key.values()
                if receipt.operation_id == operation_id
            ]
        if not matches:
            return _safe_error(404, "not_found")
        first = min(matches, key=lambda item: (item.received_at, item.receipt_id))
        content: dict[str, object] = {
            "schema_version": 1,
            "receipt_id": first.receipt_id,
            "event_id": first.event_id,
            "operation_id": first.operation_id,
            "attempt": first.attempt,
            "outcome": first.outcome,
            "severity": first.severity,
            "terminal_at": first.terminal_at,
            "received_at": first.received_at,
            "delivery_count": len(matches),
            "redaction_assertions": first.redaction_assertions,
        }
        if first.release_revision is not None and first.release_revision_source is not None:
            content["release_revision"] = first.release_revision
            content["release_revision_source"] = first.release_revision_source
        return JSONResponse(content=content)

    return app


app = create_app()
