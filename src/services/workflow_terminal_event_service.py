"""Closed classification and safe projection for durable workflow terminal events."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from src.contracts.workflow_alert_models import (
    WorkflowAlertCounts,
    WorkflowAlertDiagnosticCode,
    WorkflowAlertEnvelopeV1,
    WorkflowAlertResourceReference,
    WorkflowAlertSeverity,
    WorkflowTerminalEventV1,
    WorkflowTerminalOutcome,
    WorkflowTerminalSourceKind,
    WorkflowTypeName,
)
from src.contracts.workflow_models import IngestionResultV2, OperationType, PipelineResultV2
from src.telemetry.workflow_events import emit_workflow_terminal_telemetry

_MAX_COUNT = 9_223_372_036_854_775_807
_DIAGNOSTIC_CODE_ADAPTER = TypeAdapter(WorkflowAlertDiagnosticCode)
_OPERATION_TYPES = frozenset(
    {
        "ingestion.execute",
        "summarization.run",
        "theme_analysis.create",
        "digest.create",
        "pipeline.run",
        "podcast_script.create",
        "podcast_audio.create",
        "audio_digest.create",
    }
)


@dataclass(frozen=True)
class TerminalEventEvidence:
    """Minimal persisted intent plus immutable reconciliation identity."""

    event_id: UUID
    event_key: str
    source_kind: WorkflowTerminalSourceKind
    operation_id: int | None
    claim_generation: int | None
    terminal_status: str | None
    reconciliation_action_id: int | None
    reconciliation_run_id: UUID | None
    reconciliation_content_id: int | None
    occurred_at: datetime


@dataclass(frozen=True)
class PersistedTerminalSnapshot:
    """Closed fields selected from fresh committed persistence."""

    operation_type: str | None = None
    operation_status: str | None = None
    result: object = None
    pipeline_root_id: int | None = None
    reconciliation_reason: str | None = None


@dataclass(frozen=True)
class TerminalClassification:
    workflow_type: WorkflowTypeName
    outcome: WorkflowTerminalOutcome
    severity: WorkflowAlertSeverity
    source_kind: WorkflowTerminalSourceKind
    external_eligible: bool
    external_routed: bool
    suppression_reason: Literal["pipeline_root_aggregates"] | None = None
    resource_refs: tuple[WorkflowAlertResourceReference, ...] = ()
    source_keys: tuple[str, ...] = ()
    counts: WorkflowAlertCounts = field(default_factory=WorkflowAlertCounts)
    codes: tuple[WorkflowAlertDiagnosticCode, ...] = ()


@dataclass(frozen=True)
class ProcessedTerminalEvent:
    """Result of one idempotent pending-event processing boundary."""

    event: TerminalEventEvidence | None
    classification: TerminalClassification | None
    classification_status: Literal["ready", "telemetry_only", "rejected"]
    envelope: WorkflowAlertEnvelopeV1 | None


class WorkflowTerminalEventService:
    """Read committed safe fields, classify once, and checkpoint telemetry."""

    def __init__(
        self,
        connection: Any,
        *,
        diagnostic_origin: str | None = None,
        external_delivery_enabled: bool = False,
        telemetry_emitter: Callable[..., bool] = emit_workflow_terminal_telemetry,
    ) -> None:
        self._connection = connection
        self._diagnostic_origin = diagnostic_origin
        self._external_delivery_enabled = external_delivery_enabled
        self._telemetry_emitter = telemetry_emitter

    async def process_pending_event(
        self,
        event_id: UUID,
    ) -> ProcessedTerminalEvent | None:
        """Process one event without making telemetry or delivery authoritative."""

        row = await self._connection.fetchrow(_EVENT_QUERY, event_id)
        if row is None or row["classification_status"] != "pending":
            return None
        try:
            event = _event_from_row(row)
            snapshot = await self._fresh_snapshot(event)
            classification = classify_terminal_event(event, snapshot)
            envelope = None
            if self._external_delivery_enabled and classification.external_routed:
                if self._diagnostic_origin is None:
                    raise ValueError("enabled external delivery requires a diagnostic origin")
                envelope = project_alert_envelope(
                    event,
                    classification,
                    self._diagnostic_origin,
                )
            status: Literal["ready", "telemetry_only", "rejected"] = (
                "ready" if envelope is not None else "telemetry_only"
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            updated = await self._store_classification(
                event_id,
                classification_status="rejected",
                envelope=None,
            )
            if not updated:
                return None
            return ProcessedTerminalEvent(
                event=None,
                classification=None,
                classification_status="rejected",
                envelope=None,
            )

        updated = await self._store_classification(
            event.event_id,
            classification_status=status,
            envelope=envelope,
        )
        if not updated:
            return None

        try:
            emitted = self._telemetry_emitter(
                event_id=event.event_id,
                event_key=event.event_key,
                operation_type=classification.workflow_type,
                outcome=classification.outcome,
                severity=classification.severity,
                source_kind=classification.source_kind,
            )
        except Exception:
            emitted = False
        if emitted:
            await self._connection.execute(_TELEMETRY_CHECKPOINT_QUERY, event.event_id)
        return ProcessedTerminalEvent(
            event=event,
            classification=classification,
            classification_status=status,
            envelope=envelope,
        )

    async def _fresh_snapshot(
        self,
        event: TerminalEventEvidence,
    ) -> PersistedTerminalSnapshot:
        if event.source_kind == "operation":
            row = await self._connection.fetchrow(_OPERATION_SNAPSHOT_QUERY, event.operation_id)
            if row is None:
                raise ValueError("terminal operation no longer exists")
            result = row["result"]
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = None
            return PersistedTerminalSnapshot(
                operation_type=row["operation_type"],
                operation_status=row["operation_status"],
                result=result,
                pipeline_root_id=row["pipeline_root_id"],
            )
        if event.source_kind == "reconciliation_action":
            row = await self._connection.fetchrow(
                _RECONCILIATION_ACTION_QUERY,
                event.reconciliation_action_id,
                event.reconciliation_run_id,
                event.reconciliation_content_id,
            )
            if row is None:
                raise ValueError("reconciliation action evidence no longer exists")
            return PersistedTerminalSnapshot(reconciliation_reason=row["reason"])
        return PersistedTerminalSnapshot()

    async def _store_classification(
        self,
        event_id: UUID,
        *,
        classification_status: Literal["ready", "telemetry_only", "rejected"],
        envelope: WorkflowAlertEnvelopeV1 | None,
    ) -> bool:
        serialized = (
            json.dumps(envelope.model_dump(mode="json"), separators=(",", ":"))
            if envelope is not None
            else None
        )
        row = await self._connection.fetchrow(
            _CLASSIFICATION_UPDATE_QUERY,
            event_id,
            classification_status,
            serialized,
        )
        return row is not None


_EVENT_QUERY = """
SELECT id, event_key, source_kind, operation_id, claim_generation,
       terminal_status, reconciliation_action_id, reconciliation_run_id,
       reconciliation_content_id, classification_status, occurred_at
FROM workflow_terminal_events
WHERE id = $1
"""

_OPERATION_SNAPSHOT_QUERY = """
WITH RECURSIVE lineage AS (
    SELECT id, parent_job_id, entrypoint, payload, ARRAY[id] AS visited
    FROM pgqueuer_jobs
    WHERE id = $1
    UNION ALL
    SELECT parent.id, parent.parent_job_id, parent.entrypoint, parent.payload,
           child.visited || parent.id
    FROM pgqueuer_jobs AS parent
    JOIN lineage AS child ON parent.id = child.parent_job_id
    WHERE NOT parent.id = ANY(child.visited)
), root AS (
    SELECT id,
           CASE
             WHEN payload->>'schema_version' = '2' THEN payload->>'operation_type'
             WHEN entrypoint = 'run_pipeline' THEN 'pipeline.run'
             ELSE NULL
           END AS operation_type
    FROM lineage
    WHERE parent_job_id IS NULL
)
SELECT CASE
         WHEN job.payload->>'schema_version' = '2' THEN job.payload->>'operation_type'
         WHEN job.entrypoint IN ('ingest_content', 'extract_url_content')
           THEN 'ingestion.execute'
         WHEN job.entrypoint IN ('summarize_content', 'summarize_batch')
           THEN 'summarization.run'
         WHEN job.entrypoint IN ('analyze_themes', 'create_theme_analysis')
           THEN 'theme_analysis.create'
         WHEN job.entrypoint = 'create_digest' THEN 'digest.create'
         WHEN job.entrypoint = 'run_pipeline' THEN 'pipeline.run'
         WHEN job.entrypoint IN ('create_podcast_script', 'generate_podcast_script')
           THEN 'podcast_script.create'
         WHEN job.entrypoint IN ('create_podcast_audio', 'generate_podcast_audio')
           THEN 'podcast_audio.create'
         WHEN job.entrypoint IN ('create_audio_digest', 'generate_audio_digest')
           THEN 'audio_digest.create'
         ELSE NULL
       END AS operation_type,
       job.status AS operation_status,
       CASE WHEN job.payload->>'schema_version' = '2'
            THEN job.payload->'result' ELSE NULL END AS result,
       CASE WHEN root.id <> job.id AND root.operation_type = 'pipeline.run'
            THEN root.id ELSE NULL END AS pipeline_root_id
FROM pgqueuer_jobs AS job
LEFT JOIN root ON TRUE
WHERE job.id = $1
"""

_RECONCILIATION_ACTION_QUERY = """
SELECT reason
FROM content_reconciliation_actions
WHERE id = $1 AND run_id = $2 AND content_id = $3
"""

_CLASSIFICATION_UPDATE_QUERY = """
UPDATE workflow_terminal_events
SET classification_status = $2,
    envelope = $3::jsonb
WHERE id = $1 AND classification_status = 'pending'
RETURNING id
"""

_TELEMETRY_CHECKPOINT_QUERY = """
UPDATE workflow_terminal_events
SET telemetry_emitted_at = COALESCE(telemetry_emitted_at, NOW())
WHERE id = $1 AND telemetry_emitted_at IS NULL
"""


def _event_from_row(row: Any) -> TerminalEventEvidence:
    source_kind = row["source_kind"]
    if source_kind not in {
        "operation",
        "reconciliation_action",
        "reconciliation_failure",
    }:
        raise ValueError("terminal event has an unknown source kind")
    event_id = row["id"]
    run_id = row["reconciliation_run_id"]
    return TerminalEventEvidence(
        event_id=event_id if isinstance(event_id, UUID) else UUID(str(event_id)),
        event_key=row["event_key"],
        source_kind=cast(WorkflowTerminalSourceKind, source_kind),
        operation_id=row["operation_id"],
        claim_generation=row["claim_generation"],
        terminal_status=row["terminal_status"],
        reconciliation_action_id=row["reconciliation_action_id"],
        reconciliation_run_id=(
            run_id
            if isinstance(run_id, UUID)
            else UUID(str(run_id))
            if run_id is not None
            else None
        ),
        reconciliation_content_id=row["reconciliation_content_id"],
        occurred_at=row["occurred_at"],
    )


def classify_terminal_event(
    event: TerminalEventEvidence,
    snapshot: PersistedTerminalSnapshot,
) -> TerminalClassification:
    """Classify only closed, committed lifecycle/result evidence."""

    _validate_event_identity(event)
    if event.source_kind == "reconciliation_failure":
        return _classification(
            workflow_type="content.reconciliation",
            outcome="failed",
            source_kind=event.source_kind,
            resource_refs=_content_reference(event.reconciliation_content_id),
            codes=("apply_failed",),
        )
    if event.source_kind == "reconciliation_action":
        reason = _safe_diagnostic_code(snapshot.reconciliation_reason)
        if reason is None:
            raise ValueError("reconciliation action requires a closed reason")
        return _classification(
            workflow_type="content.reconciliation",
            outcome="reconciled",
            source_kind=event.source_kind,
            resource_refs=_content_reference(event.reconciliation_content_id),
            codes=(reason,),
        )

    operation_type = _operation_type(snapshot.operation_type)
    lifecycle = snapshot.operation_status
    if lifecycle != event.terminal_status or lifecycle not in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise ValueError("persisted operation lifecycle does not match terminal intent")
    if lifecycle == "failed":
        return _classification(
            workflow_type=operation_type,
            outcome="failed",
            source_kind=event.source_kind,
            pipeline_root_id=snapshot.pipeline_root_id,
            codes=("operation_failed",),
        )
    if lifecycle == "cancelled":
        return _classification(
            workflow_type=operation_type,
            outcome="cancelled",
            source_kind=event.source_kind,
            pipeline_root_id=snapshot.pipeline_root_id,
        )
    if operation_type == "ingestion.execute":
        return _classify_ingestion(event, snapshot)
    if operation_type == "pipeline.run":
        return _classify_pipeline(event, snapshot)
    return _classification(
        workflow_type=operation_type,
        outcome="success",
        source_kind=event.source_kind,
        pipeline_root_id=snapshot.pipeline_root_id,
    )


def build_diagnostic_url(
    trusted_origin: str,
    *,
    operation_id: int | None = None,
    event_id: UUID | None = None,
) -> str:
    """Build one exact diagnostic URL from trusted, non-user-controlled parts."""

    try:
        parsed = urlsplit(trusted_origin)
    except ValueError as exc:
        raise ValueError("invalid trusted diagnostic origin") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.hostname != parsed.hostname.encode("idna").decode("ascii")
    ):
        raise ValueError("invalid trusted diagnostic origin")
    if (operation_id is None) == (event_id is None):
        raise ValueError("diagnostic route requires exactly one closed identity")
    origin = f"https://{parsed.netloc}"
    if operation_id is not None:
        if isinstance(operation_id, bool) or operation_id <= 0:
            raise ValueError("diagnostic route requires a positive operation ID")
        return f"{origin}/api/v1/operations/{operation_id}"
    return f"{origin}/api/v1/workflow-terminal-events/{event_id}"


def project_alert_envelope(
    event: TerminalEventEvidence,
    classification: TerminalClassification,
    trusted_origin: str,
) -> WorkflowAlertEnvelopeV1:
    """Project an allowlist-first v1 external envelope or fail closed."""

    _validate_event_identity(event)
    if not classification.external_routed or classification.severity == "info":
        raise ValueError("terminal classification is not externally routable")
    if event.source_kind == "operation":
        if event.operation_id is None or event.claim_generation is None:
            raise ValueError("operation alert requires literal claim identity")
        operation_id = str(event.operation_id)
        attempt = event.claim_generation + 1
        diagnostic_url = build_diagnostic_url(
            trusted_origin,
            operation_id=event.operation_id,
        )
    else:
        operation_id = None
        attempt = 1
        diagnostic_url = build_diagnostic_url(trusted_origin, event_id=event.event_id)

    return WorkflowAlertEnvelopeV1(
        event_id=event.event_id,
        event_key=event.event_key,
        occurred_at=event.occurred_at,
        severity=cast(Literal["warning", "error"], classification.severity),
        outcome=cast(
            Literal["partial", "zero_items", "failed", "unknown", "reconciled"],
            classification.outcome,
        ),
        source_kind=event.source_kind,
        workflow_type=classification.workflow_type,
        operation_id=operation_id,
        attempt=attempt,
        diagnostic_url=diagnostic_url,
        resource_refs=list(classification.resource_refs),
        source_keys=list(classification.source_keys),
        counts=classification.counts,
        codes=list(classification.codes),
    )


def _classify_ingestion(
    event: TerminalEventEvidence,
    snapshot: PersistedTerminalSnapshot,
) -> TerminalClassification:
    try:
        result = IngestionResultV2.model_validate(snapshot.result)
    except (TypeError, ValidationError):
        return _classification(
            workflow_type="ingestion.execute",
            outcome="unknown",
            source_kind=event.source_kind,
            pipeline_root_id=snapshot.pipeline_root_id,
        )
    outcome: WorkflowTerminalOutcome = (
        result.outcome
        if result.outcome in {"success", "partial", "zero_items", "unknown"}
        else "unknown"
    )
    if outcome == "unknown" and result.outcome != "unknown":
        return _classification(
            workflow_type="ingestion.execute",
            outcome="unknown",
            source_kind=event.source_kind,
            pipeline_root_id=snapshot.pipeline_root_id,
        )

    resources, resources_omitted = _content_references(result.content_ids)
    source_keys = tuple(dict.fromkeys(item.source_key for item in result.source_outcomes))
    codes, codes_omitted = _ingestion_codes(result)
    counts = WorkflowAlertCounts(
        items_ingested=_bounded_count(result.items_ingested),
        items_skipped=_bounded_count(result.items_skipped),
        items_failed=_bounded_count(result.items_failed),
        sources_total=_bounded_count(len(result.source_outcomes) + result.source_outcomes_omitted),
        sources_omitted=_bounded_count(result.source_outcomes_omitted),
        resources_omitted=resources_omitted,
        codes_omitted=codes_omitted,
    )
    return _classification(
        workflow_type="ingestion.execute",
        outcome=outcome,
        source_kind=event.source_kind,
        pipeline_root_id=snapshot.pipeline_root_id,
        resource_refs=resources,
        source_keys=source_keys,
        counts=counts,
        codes=codes,
    )


def _classify_pipeline(
    event: TerminalEventEvidence,
    snapshot: PersistedTerminalSnapshot,
) -> TerminalClassification:
    try:
        result = PipelineResultV2.model_validate(snapshot.result)
    except (TypeError, ValidationError):
        return _classification(
            workflow_type="pipeline.run",
            outcome="unknown",
            source_kind=event.source_kind,
        )
    raw_outcome = result.ingestion_summary.outcome
    outcome: WorkflowTerminalOutcome = (
        raw_outcome if raw_outcome in {"success", "partial", "zero_items", "unknown"} else "unknown"
    )
    sources = result.ingestion_summary.sources
    counts = WorkflowAlertCounts(
        items_ingested=_bounded_count(sum(item.items_ingested or 0 for item in sources)),
        items_skipped=_bounded_count(sum(item.items_skipped or 0 for item in sources)),
        items_failed=_bounded_count(sum(item.items_failed or 0 for item in sources)),
        sources_total=_bounded_count(len(sources) + result.ingestion_summary.sources_omitted),
        sources_omitted=_bounded_count(result.ingestion_summary.sources_omitted),
    )
    return _classification(
        workflow_type="pipeline.run",
        outcome=outcome,
        source_kind=event.source_kind,
        counts=counts,
    )


def _classification(
    *,
    workflow_type: WorkflowTypeName,
    outcome: WorkflowTerminalOutcome,
    source_kind: WorkflowTerminalSourceKind,
    pipeline_root_id: int | None = None,
    resource_refs: tuple[WorkflowAlertResourceReference, ...] = (),
    source_keys: tuple[str, ...] = (),
    counts: WorkflowAlertCounts | None = None,
    codes: tuple[WorkflowAlertDiagnosticCode, ...] = (),
) -> TerminalClassification:
    if outcome == "failed":
        severity: WorkflowAlertSeverity = "error"
    elif outcome in {"partial", "zero_items", "unknown", "reconciled"}:
        severity = "warning"
    else:
        severity = "info"
    external_eligible = severity != "info"
    suppressed = external_eligible and pipeline_root_id is not None
    return TerminalClassification(
        workflow_type=workflow_type,
        outcome=outcome,
        severity=severity,
        source_kind=source_kind,
        external_eligible=external_eligible,
        external_routed=external_eligible and not suppressed,
        suppression_reason="pipeline_root_aggregates" if suppressed else None,
        resource_refs=resource_refs,
        source_keys=source_keys,
        counts=counts or WorkflowAlertCounts(),
        codes=codes,
    )


def _validate_event_identity(event: TerminalEventEvidence) -> None:
    if event.source_kind == "operation":
        WorkflowTerminalEventV1(
            event_id=event.event_id,
            event_key=event.event_key,
            source_kind=event.source_kind,
            operation_id=str(event.operation_id) if event.operation_id is not None else None,
            claim_generation=event.claim_generation,
            terminal_status=cast(
                Literal["completed", "failed", "cancelled"] | None,
                event.terminal_status,
            ),
            occurred_at=event.occurred_at,
        )
        if event.reconciliation_action_id is not None or event.reconciliation_run_id is not None:
            raise ValueError("operation terminal event contains reconciliation identity")
        if event.reconciliation_content_id is not None:
            raise ValueError("operation terminal event contains reconciliation identity")
        return

    if (
        event.operation_id is not None
        or event.claim_generation is not None
        or event.terminal_status is not None
        or event.reconciliation_run_id is None
        or event.reconciliation_content_id is None
    ):
        raise ValueError("reconciliation terminal event identity is incomplete")
    WorkflowTerminalEventV1(
        event_id=event.event_id,
        event_key=event.event_key,
        source_kind=event.source_kind,
        occurred_at=event.occurred_at,
    )
    if event.source_kind == "reconciliation_action":
        if event.reconciliation_action_id is None:
            raise ValueError("reconciliation action event requires action ID")
    elif event.reconciliation_action_id is not None:
        raise ValueError("reconciliation failure event must omit action ID")


def _operation_type(value: str | None) -> OperationType:
    if value not in _OPERATION_TYPES:
        raise ValueError("persisted operation has no closed workflow type")
    return cast(OperationType, value)


def _safe_diagnostic_code(value: str | None) -> WorkflowAlertDiagnosticCode | None:
    try:
        return _DIAGNOSTIC_CODE_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def _ingestion_codes(
    result: IngestionResultV2,
) -> tuple[tuple[WorkflowAlertDiagnosticCode, ...], int]:
    raw_codes = [
        diagnostic.code
        for diagnostics in (result.errors, result.warnings)
        for diagnostic in diagnostics
    ]
    for source in result.source_outcomes:
        raw_codes.extend(item.code for item in (*source.errors, *source.warnings))
    safe_codes = [code for value in raw_codes if (code := _safe_diagnostic_code(value))]
    unique = tuple(dict.fromkeys(safe_codes))
    declared_omitted = (
        result.errors_omitted
        + result.warnings_omitted
        + sum(item.errors_omitted + item.warnings_omitted for item in result.source_outcomes)
    )
    omitted = declared_omitted + len(raw_codes) - len(unique)
    return unique[:20], _bounded_count(omitted + max(0, len(unique) - 20))


def _content_reference(content_id: int | None) -> tuple[WorkflowAlertResourceReference, ...]:
    if content_id is None or isinstance(content_id, bool) or content_id <= 0:
        raise ValueError("reconciliation event requires a positive content ID")
    return (WorkflowAlertResourceReference(type="content", id=str(content_id)),)


def _content_references(
    values: list[int],
) -> tuple[tuple[WorkflowAlertResourceReference, ...], int]:
    identifiers = tuple(
        dict.fromkeys(
            value for value in values if not isinstance(value, bool) and 0 < value <= _MAX_COUNT
        )
    )
    selected = identifiers[:20]
    return (
        tuple(WorkflowAlertResourceReference(type="content", id=str(value)) for value in selected),
        _bounded_count(len(identifiers) - len(selected)),
    )


def _bounded_count(value: int) -> int:
    return min(max(value, 0), _MAX_COUNT)
