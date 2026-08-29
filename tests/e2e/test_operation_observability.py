"""End-to-end contract tests for the backend-neutral GX-10 trace verifier."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.gx10.verify_observability import (
    EvidenceSnapshot,
    PollPolicy,
    SubmissionIdentity,
    SubprocessLiveAdapter,
    _write_private_report,
    poll_trace_arrival,
    run_live_smoke,
    verify_snapshot,
)

TRACE_ID = "1" * 32
ROOT_OPERATION_ID = "42"
CANARY = "gx10-secret-canary-do-not-export"


def _snapshot(*, include_retry: bool = True, include_restart: bool = True) -> dict[str, object]:
    attempts = [
        {
            "operation_id": ROOT_OPERATION_ID,
            "root_operation_id": ROOT_OPERATION_ID,
            "trace_id": TRACE_ID,
            "claim_generation": 1,
            "service_name": "aca-worker",
            "carrier_source": "queue_envelope",
            "outcome": "failed" if include_retry else "succeeded",
            "telemetry_delivery_state": "delivered",
        }
    ]
    if include_retry:
        attempts.append(
            {
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
                "claim_generation": 2,
                "service_name": "aca-worker",
                "carrier_source": "persisted_queue_envelope"
                if include_restart
                else "queue_envelope",
                "outcome": "succeeded",
                "telemetry_delivery_state": "delivered",
            }
        )

    return {
        "submission": {
            "status_code": 202,
            "operation_id": ROOT_OPERATION_ID,
            "root_operation_id": ROOT_OPERATION_ID,
            "trace_id": TRACE_ID,
            "response_headers": {"X-Trace-Id": TRACE_ID},
        },
        "attempts": attempts,
        "logs": [
            {
                "service_name": "aca-api",
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
                "stage": "submit",
            },
            {
                "service_name": "aca-worker",
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
                "stage": "complete",
            },
        ],
        "observations": [
            {
                "observation_id": "root-observation",
                "parent_observation_id": None,
                "service_name": "aca-api",
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
                "claim_generation": 0,
            },
            {
                "observation_id": "worker-attempt-1",
                "parent_observation_id": "root-observation",
                "service_name": "aca-worker",
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
                "claim_generation": 1,
            },
            {
                "observation_id": "worker-attempt-2",
                "parent_observation_id": "root-observation",
                "service_name": "aca-worker",
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
                "claim_generation": 2,
                "generation": {
                    "provider": "fixture-provider",
                    "model": "fixture-model",
                    "usage": {"input_tokens": 3, "output_tokens": 2},
                },
            },
        ],
        "export_health": {
            "last_successful_export_at": "2026-08-29T18:00:00Z",
            "affected_service": "aca-worker",
        },
    }


def test_complete_snapshot_joins_api_queue_postgres_logs_and_langfuse() -> None:
    report = verify_snapshot(EvidenceSnapshot.from_mapping(_snapshot()), canaries=(CANARY,))

    assert report.ready is True
    assert report.operation_id == ROOT_OPERATION_ID
    assert report.trace_id == TRACE_ID
    assert report.checks == {
        "api_response_header": True,
        "queued_worker_hop": True,
        "postgres_attempt_rows": True,
        "correlated_logs": True,
        "langfuse_hierarchy": True,
        "generation_metadata": True,
        "retry_continuity": True,
        "restart_continuity": True,
        "secret_canaries_absent": True,
    }
    assert report.failure_codes == ()


def test_retry_and_restart_fixtures_require_monotonic_persisted_generations() -> None:
    missing_restart = verify_snapshot(
        EvidenceSnapshot.from_mapping(_snapshot(include_restart=False)), canaries=(CANARY,)
    )
    missing_retry = verify_snapshot(
        EvidenceSnapshot.from_mapping(_snapshot(include_retry=False)), canaries=(CANARY,)
    )

    assert missing_restart.ready is False
    assert "restart_context_not_persisted" in missing_restart.failure_codes
    assert missing_retry.ready is False
    assert "retry_generation_missing" in missing_retry.failure_codes


def test_secret_canary_failure_is_redacted_from_report() -> None:
    unsafe = _snapshot()
    unsafe["logs"][1]["diagnostic"] = f"provider returned {CANARY}"  # type: ignore[index]

    report = verify_snapshot(EvidenceSnapshot.from_mapping(unsafe), canaries=(CANARY,))
    serialized = report.to_json()

    assert report.ready is False
    assert "secret_canary_exposed" in report.failure_codes
    assert CANARY not in serialized
    assert "provider returned" not in serialized


def test_trace_arrival_polling_is_deterministic_and_stops_when_ready() -> None:
    snapshots = [
        EvidenceSnapshot.from_mapping({**_snapshot(), "observations": []}),
        EvidenceSnapshot.from_mapping(_snapshot()),
    ]
    sleeps: list[float] = []

    def collect() -> EvidenceSnapshot:
        return snapshots.pop(0)

    report = poll_trace_arrival(
        collect,
        canaries=(CANARY,),
        policy=PollPolicy(timeout_seconds=2.0, interval_seconds=0.25),
        monotonic=_monotonic([0.0, 0.0, 0.25]),
        sleep=sleeps.append,
    )

    assert report.ready is True
    assert sleeps == [0.25]


def test_trace_arrival_timeout_is_bounded_and_names_only_safe_health_fields() -> None:
    incomplete = _snapshot()
    incomplete["observations"] = []
    incomplete["logs"] = [{"diagnostic": CANARY * 10_000}]

    report = poll_trace_arrival(
        lambda: EvidenceSnapshot.from_mapping(incomplete),
        canaries=(CANARY,),
        policy=PollPolicy(timeout_seconds=0.5, interval_seconds=0.25, max_report_bytes=4096),
        monotonic=_monotonic([0.0, 0.0, 0.25, 0.5]),
        sleep=lambda _seconds: None,
    )
    encoded = report.to_json().encode()

    assert report.ready is False
    assert "trace_arrival_timeout" in report.failure_codes
    assert report.last_successful_export_at == "2026-08-29T18:00:00Z"
    assert report.affected_service == "aca-worker"
    assert CANARY.encode() not in encoded
    assert len(encoded) <= 4096


def test_live_smoke_submits_exactly_once_and_carries_identity_through_polling() -> None:
    incomplete = EvidenceSnapshot.from_mapping({**_snapshot(), "observations": []})
    complete = EvidenceSnapshot.from_mapping(_snapshot())

    class Adapter:
        def __init__(self) -> None:
            self.submit_calls = 0
            self.collected_identities: list[SubmissionIdentity] = []
            self.snapshots = [incomplete, complete]

        def submit(self, *, canaries: tuple[str, ...]) -> SubmissionIdentity:
            assert canaries == (CANARY,)
            self.submit_calls += 1
            return SubmissionIdentity(
                operation_id=ROOT_OPERATION_ID,
                root_operation_id=ROOT_OPERATION_ID,
                trace_id=TRACE_ID,
            )

        def collect(self, identity: SubmissionIdentity) -> EvidenceSnapshot:
            self.collected_identities.append(identity)
            return self.snapshots.pop(0)

    adapter = Adapter()
    report = run_live_smoke(
        adapter,
        canaries=(CANARY,),
        policy=PollPolicy(timeout_seconds=1.0, interval_seconds=0.25),
        monotonic=_monotonic([0.0, 0.0]),
        sleep=lambda _seconds: None,
    )

    assert adapter.submit_calls == 1
    assert adapter.collected_identities == [
        SubmissionIdentity(ROOT_OPERATION_ID, ROOT_OPERATION_ID, TRACE_ID),
        SubmissionIdentity(ROOT_OPERATION_ID, ROOT_OPERATION_ID, TRACE_ID),
    ]
    assert report.ready is True
    assert report.mode == "live"


def test_subprocess_adapter_uses_no_shell_and_only_named_environment(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setenv("GX10_TEST_OPERATOR_KEY", "operator-secret")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-forwarded")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        payload = (
            {
                "operation_id": ROOT_OPERATION_ID,
                "root_operation_id": ROOT_OPERATION_ID,
                "trace_id": TRACE_ID,
            }
            if len(calls) == 1
            else _snapshot()
        )
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = SubprocessLiveAdapter(
        submit_executable=tmp_path / "submit-adapter",
        collect_executable=tmp_path / "collect-adapter",
        env_names=("GX10_TEST_OPERATOR_KEY",),
    )

    identity = adapter.submit(canaries=(CANARY,))
    evidence = adapter.collect(identity)

    assert evidence.submission["trace_id"] == TRACE_ID
    assert json.loads(str(calls[0][1]["input"])) == {
        "canaries": [CANARY],
        "scenario": {
            "force_first_attempt_failure": True,
            "id": "gx10-observability-retry-restart-v1",
            "operation_type": "summarization.run",
            "persist_context_before_restart": True,
            "restart_before_retry": True,
        },
        "schema_version": 1,
    }
    assert calls[0][0] == [str(tmp_path / "submit-adapter")]
    assert calls[1][0] == [str(tmp_path / "collect-adapter")]
    for _command, kwargs in calls:
        assert "shell" not in kwargs
        assert kwargs["env"] == {
            "GX10_TEST_OPERATOR_KEY": "operator-secret",
            "PATH": __import__("os").environ["PATH"],
        }
        assert "operator-secret" not in str(kwargs["input"])
        assert "UNRELATED_SECRET" not in str(kwargs["env"])


def test_live_smoke_rejects_snapshot_for_a_different_submission_identity() -> None:
    wrong = _snapshot()
    wrong_trace_id = "3" * 32
    wrong["submission"].update(  # type: ignore[union-attr]
        {
            "operation_id": "43",
            "root_operation_id": "43",
            "trace_id": wrong_trace_id,
            "response_headers": {"X-Trace-Id": wrong_trace_id},
        }
    )
    for collection in ("attempts", "logs", "observations"):
        for item in wrong[collection]:  # type: ignore[union-attr]
            item.update(
                operation_id="43", root_operation_id="43", trace_id=wrong_trace_id
            )

    class WrongOperationAdapter:
        def submit(self, *, canaries: tuple[str, ...]) -> SubmissionIdentity:
            return SubmissionIdentity(ROOT_OPERATION_ID, ROOT_OPERATION_ID, TRACE_ID)

        def collect(self, identity: SubmissionIdentity) -> EvidenceSnapshot:
            return EvidenceSnapshot.from_mapping(wrong)

    report = run_live_smoke(
        WrongOperationAdapter(),
        canaries=(CANARY,),
        policy=PollPolicy(timeout_seconds=1.0),
    )

    assert report.ready is False
    assert report.failure_codes == ("submission_identity_mismatch",)
    assert report.operation_id is None
    assert report.trace_id is None
    assert "43" not in report.to_json()
    assert wrong_trace_id not in report.to_json()


def test_private_report_writer_refuses_preexisting_temporary_symlink(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    protected = tmp_path / "protected.txt"
    protected.write_text("unchanged", encoding="utf-8")
    output.with_name(f".{output.name}.tmp").symlink_to(protected)

    with pytest.raises(FileExistsError):
        _write_private_report(output, '{"ready":false}')

    assert protected.read_text(encoding="utf-8") == "unchanged"


def _monotonic(values: list[float]) -> Callable[[], float]:
    iterator = iter(values)
    last = values[-1]

    def current() -> float:
        nonlocal last
        try:
            last = next(iterator)
        except StopIteration:
            pass
        return last

    return current


def test_report_json_is_stable_for_immutable_evidence() -> None:
    evidence = EvidenceSnapshot.from_mapping(json.loads(json.dumps(_snapshot())))

    first = verify_snapshot(evidence, canaries=(CANARY,)).to_json()
    second = verify_snapshot(evidence, canaries=(CANARY,)).to_json()

    assert first == second
