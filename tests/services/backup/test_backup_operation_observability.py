from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from src.clients import operational_observability
from src.contracts.operation_context import OperationContext, bind_operation_context
from src.services.backup import engine as engine_module
from src.services.backup.engine import BackupEngine
from src.services.backup.executor import PipelineResult, Stage
from src.services.backup.models import StoreName
from src.services.backup.preflight import PreflightReport
from src.services.backup.stores import StorePlan
from src.services.backup.target import TargetConfig


class _Settings:
    environment = "test"
    backup_s3_bucket = "backup-bucket"
    backup_s3_prefix = "aca"
    backup_age_recipient = "age1recipient"


def test_backup_run_declares_a_non_payload_operational_root() -> None:
    assert BackupEngine.run.__aca_operational_entrypoint__ == (
        "backup.run",
        "backup",
        "aca-backup",
    )
    assert BackupEngine.run.__name__ == "run"
    assert not hasattr(BackupEngine.run, "__aca_capture_arguments__")


class _Span:
    def __init__(self, name: str, parent: str, attributes: dict[str, Any]) -> None:
        self.name = name
        self.span_id = f"{id(self):016x}"[-16:]
        self.parent = parent
        self.attributes = attributes


class _Provider:
    def __init__(self) -> None:
        self.stack: list[_Span] = []
        self.spans: list[_Span] = []

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        parent = self.stack[-1].span_id if self.stack else "2222222222222222"
        span = _Span(name, parent, attributes or {})
        self.spans.append(span)
        self.stack.append(span)
        try:
            yield span
        finally:
            self.stack.pop()


def _context() -> OperationContext:
    return OperationContext(
        schema_version=1,
        operation_id="41",
        root_operation_id="41",
        parent_operation_id=None,
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        trace_id="11111111111111111111111111111111",
        span_id="2222222222222222",
        claim_generation="0",
        attempt_number="1",
        entrypoint="backup.run",
        service_name="aca-backup",
        service_instance_id="backup-1",
        environment="test",
        release_revision="revision",
        stage="backup",
        resource_kind=None,
        resource_key=None,
    )


@pytest.mark.parametrize(
    ("pipeline", "remote_size", "expected_outcome", "expected_checksum"),
    [
        (PipelineResult((("pg_dump", 0),), 12, "a" * 64), 12, "succeeded", "a" * 64),
        (PipelineResult((("pg_dump", 2),)), None, "failed", None),
    ],
)
def test_backup_component_emits_real_nested_outcome_topology(
    monkeypatch: pytest.MonkeyPatch,
    pipeline: PipelineResult,
    remote_size: int | None,
    expected_outcome: str,
    expected_checksum: str | None,
) -> None:
    provider = _Provider()
    monkeypatch.setattr(operational_observability, "get_provider", lambda: provider)
    monkeypatch.setattr(engine_module, "run_pipeline", lambda _stages: pipeline)
    monkeypatch.setattr(engine_module, "stored_size", lambda _config, _key: remote_size)
    plan = StorePlan(
        StoreName.POSTGRES,
        "postgres.dump",
        stage=Stage("pg_dump", ("pg_dump",)),
    )
    config = TargetConfig(None, "bucket", "auto", "aca", None, None)

    with bind_operation_context(_context()):
        result = BackupEngine(_Settings())._run_store(
            plan,
            config=config,
            recipient="age1recipient",
            tier="daily",
            stamp="2026-08-29T000000Z",
        )

    assert str(result.outcome) == expected_outcome
    assert [span.name for span in provider.spans] == [
        "backup.component",
        "backup.component.outcome",
    ]
    component, outcome = provider.spans
    assert outcome.parent == component.span_id
    assert component.attributes["backup.component"] == "postgres"
    assert component.attributes["backup.required"] is True
    assert outcome.attributes["operation.outcome"] == expected_outcome
    assert outcome.attributes.get("backup.checksum_sha256") == expected_checksum


def test_backup_aggregate_persists_partial_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes: list[str] = []

    class _Scope:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def open(self) -> None:
            pass

        def close(self, *, outcome: str = "succeeded") -> bool:
            outcomes.append(outcome)
            return True

    monkeypatch.setattr(operational_observability, "OperationalScope", _Scope)
    monkeypatch.setattr(
        engine_module,
        "plan_all",
        lambda _settings: [
            StorePlan(StoreName.POSTGRES, "postgres.dump", skip_reason="not_configured")
        ],
    )
    monkeypatch.setattr(
        engine_module,
        "check_run_prerequisites",
        lambda _settings, _plans: PreflightReport(),
    )
    result = BackupEngine(_Settings(), now=datetime(2026, 8, 29, tzinfo=UTC)).run()

    assert result.overall_outcome == "partial"
    assert outcomes == ["partial"]
