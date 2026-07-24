"""Explicit non-production mutation tier for release verification."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic import TypeAdapter, ValidationError

from src.contracts.workflow_models import IngestCommand, OperationHandle
from src.release_smoke.models import ProtectedTargetPolicy

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_FIXTURE_ROOT = Path("tests/fixtures/release_smoke")
_MAX_FIXTURE_BYTES = 65_536
_INGEST_ADAPTER: TypeAdapter[IngestCommand] = TypeAdapter(IngestCommand)


class MutationSmokeError(RuntimeError):
    """A guarded mutation failed with stable, sanitized correlation."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MUTATION_REJECTED",
        operation_id: str | None = None,
        status: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.operation_id = operation_id
        self.status = status


@dataclass(frozen=True)
class MutationObservation:
    operation_id: str
    status: str


def derive_idempotency_key(run_id: str) -> str:
    if not _RUN_ID.fullmatch(run_id):
        raise MutationSmokeError("Run ID must be 32 lowercase hexadecimal characters")
    return f"aca-release-smoke-v1:{run_id}"


def load_mutation_fixture(repo_root: Path, fixture_name: str) -> IngestCommand:
    """Load a bounded data-only fixture beneath the checked-in fixture root."""
    requested = Path(fixture_name)
    if requested.is_absolute() or ".." in requested.parts or requested.name != fixture_name:
        raise MutationSmokeError("Mutation fixture path is outside the approved fixture root")

    root = repo_root.resolve(strict=True)
    fixture_root = (root / _FIXTURE_ROOT).resolve(strict=True)
    candidate = fixture_root / requested
    current = fixture_root
    for part in requested.parts:
        current = current / part
        if current.is_symlink():
            raise MutationSmokeError("Mutation fixture must not resolve through a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise MutationSmokeError("Mutation fixture does not exist") from exc
    if resolved.parent != fixture_root or not resolved.is_file():
        raise MutationSmokeError("Mutation fixture path is outside the approved fixture root")
    if resolved.stat().st_size > _MAX_FIXTURE_BYTES:
        raise MutationSmokeError("Mutation fixture exceeds 64 KiB")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
        return _INGEST_ADAPTER.validate_python(document)
    except (OSError, ValueError, ValidationError) as exc:
        raise MutationSmokeError("Mutation fixture is not a valid IngestCommand") from exc


def _decode_operation(response: httpx.Response, check: str) -> OperationHandle:
    if response.is_redirect:
        raise MutationSmokeError(f"{check} redirected", code="MUTATION_REDIRECT")
    if response.is_error:
        raise MutationSmokeError(
            f"{check} returned HTTP {response.status_code}",
            code="MUTATION_HTTP_ERROR",
        )
    try:
        return OperationHandle.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise MutationSmokeError(
            f"{check} returned an invalid operation",
            code="MUTATION_INVALID_OPERATION",
        ) from exc


def run_mutation(
    policy: ProtectedTargetPolicy,
    *,
    allow_mutations: bool,
    fixture_name: str,
    repo_root: Path,
    run_id: str,
    admin_key: str,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = 300.0,
    poll_interval: float = 1.0,
) -> MutationObservation:
    """Submit one canonical ingestion and require successful completion."""
    if not allow_mutations:
        raise MutationSmokeError("Mutation tier requires explicit authorization")
    if policy.target not in {"staging", "ephemeral"}:
        raise MutationSmokeError("Mutation tier requires an exact non-production target")
    fixture = load_mutation_fixture(repo_root, fixture_name)
    idempotency_key = derive_idempotency_key(run_id)

    headers = {
        "X-Admin-Key": admin_key,
        "Idempotency-Key": idempotency_key,
    }
    with httpx.Client(
        transport=transport,
        follow_redirects=False,
        timeout=20.0,
    ) as client:
        try:
            response = client.post(
                f"{policy.api_origin}/api/v1/ingestions",
                json=fixture.model_dump(mode="json", exclude_none=True),
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise MutationSmokeError(
                "Mutation submission response is ambiguous",
                code="MUTATION_AMBIGUOUS",
                status="ambiguous",
            ) from exc
        operation = _decode_operation(response, "Mutation submission")
        deadline = time.monotonic() + timeout_seconds
        while operation.status not in {"completed", "failed", "cancelled"}:
            if time.monotonic() >= deadline:
                raise MutationSmokeError(
                    "Mutation operation timed out",
                    code="MUTATION_TIMED_OUT",
                    operation_id=operation.operation_id,
                    status="timed_out",
                )
            if poll_interval:
                time.sleep(min(poll_interval, max(deadline - time.monotonic(), 0)))
            response = client.get(
                f"{policy.api_origin}/api/v1/operations/{operation.operation_id}",
                params={"wait_seconds": min(10, max(int(poll_interval), 0))},
                headers={"X-Admin-Key": admin_key},
            )
            operation = _decode_operation(response, "Mutation operation poll")

    if operation.status != "completed":
        raise MutationSmokeError(
            f"Mutation operation reached {operation.status}",
            code=f"MUTATION_{operation.status.upper()}",
            operation_id=operation.operation_id,
            status=operation.status,
        )
    return MutationObservation(
        operation_id=operation.operation_id,
        status=operation.status,
    )
