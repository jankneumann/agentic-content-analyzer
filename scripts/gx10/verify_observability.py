#!/usr/bin/env python3
"""Backend-neutral GX-10 operation-observability smoke verifier.

The verifier consumes a bounded evidence snapshot instead of querying a backend's
private schema.  Live adapters and deterministic fixtures therefore share the same
contract, checks, polling behavior, and redacted report format.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MAX_REPORT_BYTES = 16 * 1024
_PERSISTED_CARRIER_SOURCES = frozenset({"persisted_queue_envelope", "postgresql"})
_CHECK_ORDER = (
    "api_response_header",
    "queued_worker_hop",
    "postgres_attempt_rows",
    "correlated_logs",
    "langfuse_hierarchy",
    "generation_metadata",
    "retry_continuity",
    "restart_continuity",
    "secret_canaries_absent",
)
_FAILURE_BY_CHECK = {
    "api_response_header": "api_trace_header_mismatch",
    "queued_worker_hop": "queued_worker_hop_missing",
    "postgres_attempt_rows": "postgres_attempt_evidence_missing",
    "correlated_logs": "correlated_logs_missing",
    "langfuse_hierarchy": "langfuse_hierarchy_missing",
    "generation_metadata": "generation_metadata_missing",
    "retry_continuity": "retry_generation_missing",
    "restart_continuity": "restart_context_not_persisted",
    "secret_canaries_absent": "secret_canary_exposed",
}


JsonMapping = Mapping[str, Any]


class EvidenceCollector(Protocol):
    """Backend adapter boundary used by the polling orchestrator."""

    def collect(self) -> EvidenceSnapshot:
        """Return the latest bounded evidence for one synthetic operation."""


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    """Backend-neutral evidence required by scenarios GX10-011 and GX10-012."""

    submission: JsonMapping
    attempts: tuple[JsonMapping, ...]
    logs: tuple[JsonMapping, ...]
    observations: tuple[JsonMapping, ...]
    export_health: JsonMapping

    @classmethod
    def from_mapping(cls, value: JsonMapping) -> EvidenceSnapshot:
        return cls(
            submission=_mapping(value.get("submission")),
            attempts=_mapping_tuple(value.get("attempts")),
            logs=_mapping_tuple(value.get("logs")),
            observations=_mapping_tuple(value.get("observations")),
            export_health=_mapping(value.get("export_health")),
        )

    def searchable_json(self) -> str:
        """Serialize only for exact canary scanning; never include this in reports."""

        return json.dumps(
            {
                "submission": self.submission,
                "attempts": self.attempts,
                "logs": self.logs,
                "observations": self.observations,
                "export_health": self.export_health,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )


@dataclass(frozen=True, slots=True)
class PollPolicy:
    timeout_seconds: float = 30.0
    interval_seconds: float = 0.5
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES

    def __post_init__(self) -> None:
        if self.timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.max_report_bytes < 1024:
            raise ValueError("max_report_bytes must be at least 1024")


@dataclass(frozen=True, slots=True)
class VerificationReport:
    schema_version: int
    mode: str
    ready: bool
    operation_id: str | None
    trace_id: str | None
    checks: Mapping[str, bool]
    failure_codes: tuple[str, ...]
    last_successful_export_at: str | None
    affected_service: str | None
    timed_out: bool = False
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "ready": self.ready,
            "operation_id": self.operation_id,
            "trace_id": self.trace_id,
            "checks": dict(self.checks),
            "failure_codes": list(self.failure_codes),
            "last_successful_export_at": self.last_successful_export_at,
            "affected_service": self.affected_service,
            "timed_out": self.timed_out,
        }

    def to_json(self) -> str:
        encoded = json.dumps(
            self.to_mapping(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        if len(encoded.encode("utf-8")) > self.max_report_bytes:
            raise ValueError("verification report exceeds configured byte bound")
        return encoded


def verify_snapshot(
    snapshot: EvidenceSnapshot,
    *,
    canaries: Sequence[str] = (),
    mode: str = "fixture",
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES,
) -> VerificationReport:
    """Verify a snapshot without exposing evidence payloads in the result."""

    operation_id = _safe_identifier(snapshot.submission.get("operation_id"), 64)
    root_operation_id = _safe_identifier(snapshot.submission.get("root_operation_id"), 64)
    trace_id = _safe_identifier(snapshot.submission.get("trace_id"), 32)
    identity = (operation_id, root_operation_id, trace_id)

    headers = {
        str(key).lower(): _safe_identifier(value, 128)
        for key, value in _mapping(snapshot.submission.get("response_headers")).items()
    }
    api_response_header = bool(
        snapshot.submission.get("status_code") == 202
        and operation_id
        and operation_id == root_operation_id
        and _is_trace_id(trace_id)
        and headers.get("x-trace-id") == trace_id
    )

    matching_attempts = tuple(
        attempt for attempt in snapshot.attempts if _matches_identity(attempt, identity)
    )
    generations = tuple(_generation(attempt) for attempt in matching_attempts)
    valid_generations = all(generation is not None for generation in generations)
    ordered_generations = tuple(generation for generation in generations if generation is not None)
    postgres_attempt_rows = bool(
        matching_attempts
        and len(matching_attempts) == len(snapshot.attempts)
        and valid_generations
        and ordered_generations == tuple(sorted(set(ordered_generations)))
        and all(_safe_identifier(item.get("service_name"), 128) for item in matching_attempts)
    )
    queued_worker_hop = any(
        _safe_identifier(attempt.get("service_name"), 128) == "aca-worker"
        and _safe_identifier(attempt.get("carrier_source"), 64)
        in {"queue_envelope", *_PERSISTED_CARRIER_SOURCES}
        for attempt in matching_attempts
    )

    correlated_log_services = {
        _safe_identifier(item.get("service_name"), 128)
        for item in snapshot.logs
        if _matches_identity(item, identity)
    }
    correlated_logs = {"aca-api", "aca-worker"}.issubset(correlated_log_services)

    matching_observations = tuple(
        observation
        for observation in snapshot.observations
        if _matches_identity(observation, identity)
    )
    observation_ids = {
        _safe_identifier(item.get("observation_id"), 128) for item in matching_observations
    }
    root_ids = {
        _safe_identifier(item.get("observation_id"), 128)
        for item in matching_observations
        if item.get("parent_observation_id") is None
        and _safe_identifier(item.get("service_name"), 128) == "aca-api"
    }
    worker_children = tuple(
        item
        for item in matching_observations
        if _safe_identifier(item.get("service_name"), 128) == "aca-worker"
        and _safe_identifier(item.get("parent_observation_id"), 128) in root_ids
    )
    langfuse_hierarchy = bool(
        root_ids
        and worker_children
        and len(matching_observations) == len(snapshot.observations)
        and root_ids.issubset(observation_ids)
    )
    generation_metadata = any(_has_generation_metadata(item) for item in worker_children)

    retry_continuity = bool(
        len(matching_attempts) >= 2
        and len(ordered_generations) >= 2
        and all(later > earlier for earlier, later in itertools.pairwise(ordered_generations))
    )
    restart_continuity = any(
        _safe_identifier(item.get("carrier_source"), 64) in _PERSISTED_CARRIER_SOURCES
        for item in matching_attempts[1:]
    )
    nonempty_canaries = tuple(canary for canary in canaries if canary)
    searchable = snapshot.searchable_json()
    secret_canaries_absent = not any(canary in searchable for canary in nonempty_canaries)

    checks = {
        "api_response_header": api_response_header,
        "queued_worker_hop": queued_worker_hop,
        "postgres_attempt_rows": postgres_attempt_rows,
        "correlated_logs": correlated_logs,
        "langfuse_hierarchy": langfuse_hierarchy,
        "generation_metadata": generation_metadata,
        "retry_continuity": retry_continuity,
        "restart_continuity": restart_continuity,
        "secret_canaries_absent": secret_canaries_absent,
    }
    ordered_checks = {name: bool(checks[name]) for name in _CHECK_ORDER}
    failure_codes = tuple(
        _FAILURE_BY_CHECK[name] for name in _CHECK_ORDER if not ordered_checks[name]
    )
    health = snapshot.export_health
    return VerificationReport(
        schema_version=1,
        mode=mode,
        ready=not failure_codes,
        operation_id=operation_id,
        trace_id=trace_id,
        checks=ordered_checks,
        failure_codes=failure_codes,
        last_successful_export_at=_safe_timestamp(health.get("last_successful_export_at")),
        affected_service=_safe_service(health.get("affected_service")),
        max_report_bytes=max_report_bytes,
    )


def poll_trace_arrival(
    collect: Callable[[], EvidenceSnapshot],
    *,
    canaries: Sequence[str] = (),
    policy: PollPolicy = PollPolicy(),
    mode: str = "fixture",
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> VerificationReport:
    """Poll bounded evidence until all checks pass or the deadline expires."""

    started = monotonic()
    while True:
        report = verify_snapshot(
            collect(), canaries=canaries, mode=mode, max_report_bytes=policy.max_report_bytes
        )
        if report.ready:
            return report
        if monotonic() - started >= policy.timeout_seconds:
            failures = (*report.failure_codes, "trace_arrival_timeout")
            return replace(
                report,
                ready=False,
                failure_codes=tuple(dict.fromkeys(failures)),
                timed_out=True,
            )
        sleep(policy.interval_seconds)


class FixtureEvidenceCollector:
    """Deterministic adapter for contract tests and offline GX-10 rehearsal."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def collect(self) -> EvidenceSnapshot:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("fixture root must be a JSON object")
        return EvidenceSnapshot.from_mapping(raw)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--canary", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--interval-seconds", type=float, default=0.25)
    parser.add_argument("--max-report-bytes", type=int, default=DEFAULT_MAX_REPORT_BYTES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    collector = FixtureEvidenceCollector(args.fixture)
    report = poll_trace_arrival(
        collector.collect,
        canaries=args.canary,
        policy=PollPolicy(
            timeout_seconds=args.timeout_seconds,
            interval_seconds=args.interval_seconds,
            max_report_bytes=args.max_report_bytes,
        ),
        mode="fixture",
    )
    _write_private_report(args.output, report.to_json())
    return 0 if report.ready else 1


def _write_private_report(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(payload + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _mapping(value: object) -> JsonMapping:
    return value if isinstance(value, Mapping) else {}


def _mapping_tuple(value: object) -> tuple[JsonMapping, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _safe_identifier(value: object, max_length: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > max_length:
        return None
    if not all(character.isalnum() or character in "._:-" for character in value):
        return None
    return value


def _safe_timestamp(value: object) -> str | None:
    candidate = _safe_identifier(value, 64)
    return candidate if candidate and "T" in candidate else None


def _safe_service(value: object) -> str | None:
    return _safe_identifier(value, 128)


def _is_trace_id(value: str | None) -> bool:
    return bool(
        value
        and len(value) == 32
        and value != "0" * 32
        and all(c in "0123456789abcdef" for c in value)
    )


def _matches_identity(
    item: JsonMapping, identity: tuple[str | None, str | None, str | None]
) -> bool:
    operation_id, root_operation_id, trace_id = identity
    return bool(
        operation_id
        and root_operation_id
        and trace_id
        and _safe_identifier(item.get("operation_id"), 64) == operation_id
        and _safe_identifier(item.get("root_operation_id"), 64) == root_operation_id
        and _safe_identifier(item.get("trace_id"), 32) == trace_id
    )


def _generation(item: JsonMapping) -> int | None:
    value = item.get("claim_generation")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _has_generation_metadata(observation: JsonMapping) -> bool:
    generation = _mapping(observation.get("generation"))
    usage = _mapping(generation.get("usage"))
    return bool(
        _safe_identifier(generation.get("provider"), 128)
        and _safe_identifier(generation.get("model"), 128)
        and isinstance(usage.get("input_tokens"), int)
        and isinstance(usage.get("output_tokens"), int)
    )


if __name__ == "__main__":
    raise SystemExit(main())
