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
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MAX_REPORT_BYTES = 16 * 1024
DEFAULT_MAX_ADAPTER_BYTES = 1024 * 1024
_PERSISTED_CARRIER_SOURCES = frozenset({"persisted_queue_envelope", "postgresql"})
_CANONICAL_ATTEMPT_OUTCOMES = frozenset(
    {
        "succeeded",
        "partial",
        "skipped_policy",
        "skipped_duplicate",
        "filtered",
        "retryable_failure",
        "permanent_failure",
        "cancelled",
    }
)
_CHECK_ORDER = (
    "api_response_header",
    "queued_worker_hop",
    "postgres_attempt_rows",
    "attempt_outcomes_valid",
    "correlated_logs",
    "langfuse_hierarchy",
    "generation_metadata",
    "retry_continuity",
    "restart_continuity",
    "secret_canaries_absent",
    "export_health_proof",
)
_FAILURE_BY_CHECK = {
    "api_response_header": "api_trace_header_mismatch",
    "queued_worker_hop": "queued_worker_hop_missing",
    "postgres_attempt_rows": "postgres_attempt_evidence_missing",
    "attempt_outcomes_valid": "attempt_outcome_invalid",
    "correlated_logs": "correlated_logs_missing",
    "langfuse_hierarchy": "langfuse_hierarchy_missing",
    "generation_metadata": "generation_metadata_missing",
    "retry_continuity": "retry_generation_missing",
    "restart_continuity": "restart_context_not_persisted",
    "secret_canaries_absent": "secret_canary_exposed",
    "export_health_proof": "export_health_missing",
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
class SubmissionIdentity:
    """Opaque identity returned once by the live synthetic submit adapter."""

    operation_id: str
    root_operation_id: str
    trace_id: str

    @classmethod
    def from_mapping(cls, value: JsonMapping) -> SubmissionIdentity:
        operation_id = _safe_identifier(value.get("operation_id"), 64)
        root_operation_id = _safe_identifier(value.get("root_operation_id"), 64)
        trace_id = _safe_identifier(value.get("trace_id"), 32)
        if not operation_id or not root_operation_id or not _is_trace_id(trace_id):
            raise AdapterCommandError("adapter_submit_invalid")
        assert trace_id is not None
        return cls(operation_id, root_operation_id, trace_id)

    def to_mapping(self) -> dict[str, str]:
        return {
            "operation_id": self.operation_id,
            "root_operation_id": self.root_operation_id,
            "trace_id": self.trace_id,
        }


class LiveEvidenceAdapter(Protocol):
    """Backend-neutral boundary for a real synthetic submission and evidence poll."""

    def submit(self, *, canaries: tuple[str, ...]) -> SubmissionIdentity: ...

    def collect(self, identity: SubmissionIdentity) -> EvidenceSnapshot: ...


class AdapterCommandError(RuntimeError):
    """Safe fixed-code adapter failure; command output is deliberately discarded."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SubprocessLiveAdapter:
    """Invoke explicit adapters with JSON stdin/stdout, never a shell or secret argv."""

    def __init__(
        self,
        *,
        submit_executable: Path,
        collect_executable: Path,
        env_names: Sequence[str] = (),
        command_timeout_seconds: float = 30.0,
        max_response_bytes: int = DEFAULT_MAX_ADAPTER_BYTES,
    ) -> None:
        if not submit_executable.is_absolute() or not collect_executable.is_absolute():
            raise ValueError("live adapter executable paths must be absolute")
        if command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be positive")
        if max_response_bytes < 1024:
            raise ValueError("max_response_bytes must be at least 1024")
        self._submit_executable = submit_executable
        self._collect_executable = collect_executable
        self._env_names = tuple(dict.fromkeys(env_names))
        self._command_timeout_seconds = command_timeout_seconds
        self._max_response_bytes = max_response_bytes

    def submit(self, *, canaries: tuple[str, ...]) -> SubmissionIdentity:
        response = self._invoke(
            self._submit_executable,
            {
                "schema_version": 1,
                "scenario": {
                    "id": "gx10-observability-retry-restart-v1",
                    "operation_type": "summarization.run",
                    "force_first_attempt_failure": True,
                    "persist_context_before_restart": True,
                    "restart_before_retry": True,
                },
                "canaries": list(canaries),
            },
            failure_code="adapter_submit_failed",
        )
        return SubmissionIdentity.from_mapping(response)

    def collect(self, identity: SubmissionIdentity) -> EvidenceSnapshot:
        response = self._invoke(
            self._collect_executable,
            {"schema_version": 1, "identity": identity.to_mapping()},
            failure_code="adapter_collect_failed",
        )
        return EvidenceSnapshot.from_mapping(response)

    def _invoke(self, executable: Path, request: JsonMapping, *, failure_code: str) -> JsonMapping:
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        for name in self._env_names:
            if not _is_env_name(name) or name not in os.environ:
                raise AdapterCommandError(failure_code)
            environment[name] = os.environ[name]
        try:
            completed = subprocess.run(
                [str(executable)],
                input=json.dumps(request, sort_keys=True, separators=(",", ":")),
                text=True,
                capture_output=True,
                env=environment,
                cwd="/",
                timeout=self._command_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AdapterCommandError(failure_code) from exc
        if completed.returncode != 0:
            raise AdapterCommandError(failure_code)
        if len(completed.stdout.encode("utf-8")) > self._max_response_bytes:
            raise AdapterCommandError(failure_code)
        try:
            decoded = json.loads(completed.stdout)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise AdapterCommandError(failure_code) from exc
        if not isinstance(decoded, dict):
            raise AdapterCommandError(failure_code)
        return decoded


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
    attempt_outcomes_valid = bool(
        matching_attempts
        and all(
            item.get("outcome") is None
            or (
                isinstance(item.get("outcome"), str)
                and item.get("outcome") in _CANONICAL_ATTEMPT_OUTCOMES
            )
            for item in matching_attempts
        )
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
        and any(
            earlier.get("outcome") == "retryable_failure" and later.get("outcome") == "succeeded"
            for earlier_index, earlier in enumerate(matching_attempts[:-1])
            for later in matching_attempts[earlier_index + 1 :]
        )
    )
    restart_continuity = any(
        _safe_identifier(item.get("carrier_source"), 64) in _PERSISTED_CARRIER_SOURCES
        for item in matching_attempts[1:]
    )
    nonempty_canaries = tuple(canary for canary in canaries if canary)
    searchable = snapshot.searchable_json()
    secret_canaries_absent = not any(canary in searchable for canary in nonempty_canaries)
    health = snapshot.export_health
    last_successful_export_at = _safe_timestamp(health.get("last_successful_export_at"))
    affected_service = _safe_service(health.get("affected_service"))
    export_health_proof = bool(last_successful_export_at and affected_service)

    checks = {
        "api_response_header": api_response_header,
        "queued_worker_hop": queued_worker_hop,
        "postgres_attempt_rows": postgres_attempt_rows,
        "attempt_outcomes_valid": attempt_outcomes_valid,
        "correlated_logs": correlated_logs,
        "langfuse_hierarchy": langfuse_hierarchy,
        "generation_metadata": generation_metadata,
        "retry_continuity": retry_continuity,
        "restart_continuity": restart_continuity,
        "secret_canaries_absent": secret_canaries_absent,
        "export_health_proof": export_health_proof,
    }
    ordered_checks = {name: bool(checks[name]) for name in _CHECK_ORDER}
    failure_codes = tuple(
        _FAILURE_BY_CHECK[name] for name in _CHECK_ORDER if not ordered_checks[name]
    )
    return VerificationReport(
        schema_version=1,
        mode=mode,
        ready=not failure_codes,
        operation_id=operation_id,
        trace_id=trace_id,
        checks=ordered_checks,
        failure_codes=failure_codes,
        last_successful_export_at=last_successful_export_at,
        affected_service=affected_service,
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


def run_live_smoke(
    adapter: LiveEvidenceAdapter,
    *,
    canaries: Sequence[str],
    policy: PollPolicy,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> VerificationReport:
    """Submit exactly once, then poll all evidence using only returned identity."""

    fixed_canaries = tuple(canaries)
    identity = adapter.submit(canaries=fixed_canaries)

    def collect_submitted_operation() -> EvidenceSnapshot:
        snapshot = adapter.collect(identity)
        submission = snapshot.submission
        if (
            _safe_identifier(submission.get("operation_id"), 64) != identity.operation_id
            or _safe_identifier(submission.get("root_operation_id"), 64)
            != identity.root_operation_id
            or _safe_identifier(submission.get("trace_id"), 32) != identity.trace_id
        ):
            raise _SubmissionIdentityMismatchError
        return snapshot

    try:
        return poll_trace_arrival(
            collect_submitted_operation,
            canaries=fixed_canaries,
            policy=policy,
            mode="live",
            monotonic=monotonic,
            sleep=sleep,
        )
    except _SubmissionIdentityMismatchError:
        return _safe_failure_report("submission_identity_mismatch", mode="live", policy=policy)


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
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--live-submit-command", type=Path)
    parser.add_argument("--live-collect-command", type=Path)
    parser.add_argument("--adapter-env-name", action="append", default=[])
    parser.add_argument("--canary-env-name", action="append", default=[])
    parser.add_argument("--canary", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--interval-seconds", type=float, default=0.25)
    parser.add_argument("--max-report-bytes", type=int, default=DEFAULT_MAX_REPORT_BYTES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    live_requested = args.live_submit_command is not None or args.live_collect_command is not None
    if args.fixture is not None and live_requested:
        parser.error("choose fixture mode or live command mode, not both")
    if args.fixture is None and not live_requested:
        parser.error("fixture mode or both live commands are required")
    if live_requested and (args.live_submit_command is None or args.live_collect_command is None):
        parser.error("live mode requires both submit and collect commands")
    if live_requested and args.canary:
        parser.error("live canaries must come from --canary-env-name, not command arguments")

    timeout_seconds = args.timeout_seconds
    if timeout_seconds is None:
        timeout_seconds = 30.0 if live_requested else 0.0
    policy = PollPolicy(
        timeout_seconds=timeout_seconds,
        interval_seconds=args.interval_seconds,
        max_report_bytes=args.max_report_bytes,
    )
    mode = "live" if live_requested else "fixture"
    try:
        if live_requested:
            canaries = _named_environment_values(args.canary_env_name)
            adapter = SubprocessLiveAdapter(
                submit_executable=args.live_submit_command,
                collect_executable=args.live_collect_command,
                env_names=args.adapter_env_name,
            )
            report = run_live_smoke(adapter, canaries=canaries, policy=policy)
        else:
            collector = FixtureEvidenceCollector(args.fixture)
            report = poll_trace_arrival(
                collector.collect,
                canaries=args.canary,
                policy=policy,
                mode="fixture",
            )
    except AdapterCommandError as exc:
        report = _safe_failure_report(exc.code, mode=mode, policy=policy)
    except (OSError, ValueError, json.JSONDecodeError):
        report = _safe_failure_report("evidence_adapter_invalid", mode=mode, policy=policy)
    _write_private_report(args.output, report.to_json())
    return 0 if report.ready else 1


def _write_private_report(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _safe_failure_report(code: str, *, mode: str, policy: PollPolicy) -> VerificationReport:
    return VerificationReport(
        schema_version=1,
        mode=mode,
        ready=False,
        operation_id=None,
        trace_id=None,
        checks=dict.fromkeys(_CHECK_ORDER, False),
        failure_codes=(code,),
        last_successful_export_at=None,
        affected_service=None,
        max_report_bytes=policy.max_report_bytes,
    )


def _named_environment_values(names: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for name in names:
        if not _is_env_name(name) or name not in os.environ or not os.environ[name]:
            raise AdapterCommandError("canary_environment_missing")
        values.append(os.environ[name])
    return tuple(values)


def _is_env_name(value: str) -> bool:
    return bool(
        value
        and value[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
        and all(character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for character in value)
    )


class _SubmissionIdentityMismatchError(Exception):
    """Internal control flow; no evidence fields are attached by design."""


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
    if not isinstance(value, str) or not value or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


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
