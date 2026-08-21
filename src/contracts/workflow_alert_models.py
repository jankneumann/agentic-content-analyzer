"""Closed contracts for durable workflow terminal events and external alerts."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AnyUrl,
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    UrlConstraints,
    field_validator,
    model_serializer,
    model_validator,
)

from src.contracts.workflow_models import (
    ContentReconciliationReason,
    OperationType,
    StrictModel,
    TerminalOperationStatus,
)

WorkflowTerminalOutcome = Literal[
    "success", "partial", "zero_items", "cancelled", "failed", "unknown", "reconciled"
]
WorkflowAlertSeverity = Literal["info", "warning", "error"]
WorkflowAlertExternalSeverity = Literal["warning", "error"]
WorkflowTerminalSourceKind = Literal[
    "operation",
    "reconciliation_action",
    "reconciliation_failure",
    # A system check is not a workflow. It has no operation, no claim, and no
    # reconciliation identity, which is exactly why widening this literal alone was
    # not enough: six further closed points in this module and three in the
    # emitting service reject it. See the `system_check` branches below.
    "system_check",
]
WorkflowAlertDeliveryStatus = Literal[
    "pending", "leased", "delivered", "permanent_failure", "exhausted"
]
WorkflowReleaseRevision = Annotated[
    str,
    Field(pattern="^(?:[a-f0-9]{40}|development|unavailable)$", max_length=40),
]
WorkflowReleaseRevisionSource = Literal["railway_commit_sha", "local_development", "unavailable"]

BoundedPositiveIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=19, pattern="^[1-9][0-9]*$"),
]
WorkflowEventKey = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern="^[a-z0-9:_-]+$"),
]
WorkflowTypeName = OperationType | Literal["content.reconciliation", "system.backup_freshness"]
WorkflowAlertResourceType = Literal[
    "content",
    "ingestion_run",
    "summary_batch",
    "theme_analysis",
    "digest",
    "pipeline_run",
    "podcast_script",
    "podcast",
    "audio_digest",
]
WorkflowAlertDiagnosticCode = (
    ContentReconciliationReason
    | Literal[
        "arxiv_paper_error",
        "arxiv_source_error",
        "channel_ingest_error",
        "channel_unresolvable",
        "empty_response",
        "extraction_failed",
        "feed_ingest_error",
        "feed_redirected",
        "fetch_error",
        "file_ingest_error",
        "file_not_found",
        "invalid_youtube_playlist",
        "invalid_youtube_url",
        "oauth_unavailable",
        "operation_failed",
        "parse_error",
        "persistence_error",
        "playlist_ingest_error",
        "scholar_paper_error",
        "scholar_source_error",
        "search_failed",
        "source_partial",
        "storage_error",
        "unexpected_error",
        "video_processing_error",
        "youtube_metadata_failed",
        "youtube_video_not_found",
        # Obsidian vault ingestion. Every code below is a fixed literal chosen by
        # the parser, scanner, or adapter — none is derived from a note's path,
        # URL, frontmatter, or body — so allowlisting them keeps vault alerts
        # actionable without widening what can leave the worker.
        "body_too_large",
        "directory_unavailable",
        "file_unavailable",
        "file_unstable",
        "frontmatter_not_mapping",
        "frontmatter_too_large",
        "invalid_capture_client",
        "invalid_captured_at",
        "invalid_content_type_hint",
        "invalid_cursor",
        "invalid_encoding",
        "invalid_frontmatter",
        "invalid_scan_limits",
        "invalid_url",
        "missing_frontmatter",
        "missing_required_metadata",
        "non_regular_file",
        "normalization_collision",
        "note_too_large",
        "retry_exhausted",
        "scan_byte_limit",
        "scan_depth_limit",
        "scan_duration_limit",
        "scan_entry_limit",
        "scan_file_limit",
        "source_unavailable",
        "unsafe_path",
        "yaml_alias_limit",
        "yaml_custom_tag",
        "yaml_depth_limit",
        "yaml_duplicate_key",
        "yaml_invalid",
        "yaml_node_limit",
        "yaml_string_limit",
        "yaml_unsupported_type",
        # Backup freshness. The AUTHORITATIVE set for these lives in
        # openspec/contracts/backup/events/backup-freshness-alert.schema.json —
        # this list must admit exactly those codes, which
        # tests/contract/test_workflow_alert_contracts.py asserts mechanically.
        # The set drifted three times during planning while it was enumerated in
        # three places; the schema is now the only place it is decided.
        "backup_environment_mismatch",
        "backup_no_history",
        "backup_partial",
        "backup_stale",
        "backup_target_unreachable",
    ]
)
WorkflowDiagnosticUrl = Annotated[
    AnyUrl,
    UrlConstraints(max_length=2048, allowed_schemes=["https"]),
]

#: A2/A10 — the ONE system-check event-key grammar, stated here and referenced
#: everywhere else. Both earlier candidate grammars embedded an ISO-8601 stamp,
#: whose uppercase `T`/`Z` fail `WorkflowEventKey` — so every alert would have
#: failed at construction, and the two candidates disagreed with each other.
#:
#: The suffix is the START of the fixed-length check window containing the
#: evaluation, not a wall-clock read at emission time. Every evaluation inside one
#: window therefore derives the identical key however often the worker ticks, which
#: is what makes the durable path deduplicate per window. The condition — stale,
#: no-history, partial — travels in `codes`, so one grammar covers every case
#: without breaking that idempotency.
SYSTEM_CHECK_EVENT_KEY_PATTERN = r"system_check:backup_freshness:[0-9]+"


class WorkflowTerminalEventV1(StrictModel):
    """Minimal safe terminal intent read from the durable outbox."""

    schema_version: Literal[1] = 1
    event_id: UUID
    event_key: WorkflowEventKey
    source_kind: WorkflowTerminalSourceKind
    operation_id: BoundedPositiveIdentifier | None = None
    claim_generation: Annotated[int, Field(ge=0, le=2_147_483_647)] | None = None
    terminal_status: TerminalOperationStatus | None = None
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def validate_source_identity(self) -> WorkflowTerminalEventV1:
        if self.source_kind == "operation":
            if (
                self.operation_id is None
                or self.claim_generation is None
                or self.terminal_status is None
            ):
                raise ValueError("operation terminal events require operation claim identity")
            expected_key = (
                f"operation:{self.operation_id}:claim:{self.claim_generation}:"
                f"status:{self.terminal_status}"
            )
            if self.event_key != expected_key:
                raise ValueError("operation terminal event_key must match literal claim identity")
            return self

        if (
            self.operation_id is not None
            or self.claim_generation is not None
            or self.terminal_status is not None
        ):
            raise ValueError("non-operation terminal events must omit operation claim fields")

        if self.source_kind == "system_check":
            # A13 point 9. An earlier revision dismissed this class as "a different
            # class entirely" and widened only the alert envelope. It is on the
            # emission path: `_validate_event_identity` instantiates it, so a
            # system_check event that never reaches this branch is rejected before
            # an envelope is ever constructed — silently, as a rejected row.
            if re.fullmatch(SYSTEM_CHECK_EVENT_KEY_PATTERN, self.event_key) is None:
                raise ValueError("system check terminal event_key has an invalid identity")
            return self

        if self.source_kind == "reconciliation_action":
            valid_key = re.fullmatch(r"reconciliation-action:[1-9][0-9]*", self.event_key)
        else:
            valid_key = re.fullmatch(
                r"reconciliation-failure:"
                r"[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-"
                r"[89ab][a-f0-9]{3}-[a-f0-9]{12}:"
                r"content:[1-9][0-9]*:reason:apply_failed",
                self.event_key,
            )
        if valid_key is None:
            raise ValueError("reconciliation terminal event_key has an invalid identity")
        return self


class WorkflowAlertResourceReference(StrictModel):
    type: WorkflowAlertResourceType
    id: BoundedPositiveIdentifier


class WorkflowAlertCounts(StrictModel):
    items_ingested: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    items_skipped: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    items_failed: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    sources_total: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    sources_omitted: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    resources_omitted: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    codes_omitted: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    # Backup-freshness tallies. This is a StrictModel with extra="forbid", so a
    # system_check alert carrying `manifest_age_seconds` is rejected at
    # CONSTRUCTION unless the field exists here — widening `source_kind` alone
    # would have produced an alert that could never be built.
    manifest_age_seconds: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    stores_succeeded: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    stores_failed: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    stores_skipped: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_counts(cls, value: object) -> object:
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("workflow alert counts must be omitted rather than null")
        return value

    @model_serializer(mode="wrap")
    def serialize_without_nulls(
        self,
        serializer: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        return {key: value for key, value in serializer(self).items() if value is not None}


class WorkflowAlertEnvelopeV1(StrictModel):
    """Closed, allowlist-first body accepted by external alert sinks."""

    schema_version: Literal[1] = 1
    event_id: UUID
    event_key: WorkflowEventKey
    occurred_at: AwareDatetime
    severity: WorkflowAlertExternalSeverity
    outcome: Literal["partial", "zero_items", "failed", "unknown", "reconciled"]
    source_kind: WorkflowTerminalSourceKind
    workflow_type: WorkflowTypeName
    release_revision: WorkflowReleaseRevision | None = None
    release_revision_source: WorkflowReleaseRevisionSource | None = None
    operation_id: BoundedPositiveIdentifier | None
    attempt: Annotated[int, Field(ge=1, le=2_147_483_648)]
    diagnostic_url: WorkflowDiagnosticUrl
    resource_refs: Annotated[list[WorkflowAlertResourceReference], Field(max_length=20)]
    source_keys: Annotated[
        list[Annotated[str, Field(pattern="^src_[a-f0-9]{20}$")]],
        Field(max_length=100),
    ]
    counts: WorkflowAlertCounts
    codes: Annotated[list[WorkflowAlertDiagnosticCode], Field(max_length=20)]

    @model_serializer(mode="wrap")
    def serialize_legacy_compatible(
        self,
        serializer: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        serialized: dict[str, Any] = serializer(self)
        if self.release_revision is None:
            serialized.pop("release_revision", None)
            serialized.pop("release_revision_source", None)
        return serialized

    @field_validator("diagnostic_url")
    @classmethod
    def validate_diagnostic_route(cls, value: AnyUrl) -> AnyUrl:
        path = value.path or ""
        operation_id = path.removeprefix("/api/v1/operations/")
        operation_path = (
            path.startswith("/api/v1/operations/")
            and operation_id.isascii()
            and operation_id.isdigit()
        )
        event_path = path.startswith("/api/v1/workflow-terminal-events/") and _is_canonical_uuid(
            path.removeprefix("/api/v1/workflow-terminal-events/")
        )
        if (
            value.username is not None
            or value.password is not None
            or value.query is not None
            or value.fragment is not None
            or not (operation_path or event_path)
        ):
            raise ValueError("workflow alert diagnostic_url must use an allowlisted route")
        if operation_path and operation_id.startswith("0"):
            raise ValueError("workflow alert diagnostic_url requires a positive operation ID")
        return value

    @model_validator(mode="after")
    def validate_closed_identity_and_collections(self) -> WorkflowAlertEnvelopeV1:
        if (self.release_revision is None) != (self.release_revision_source is None):
            raise ValueError("release revision and provenance must be present together")
        if self.release_revision is None or self.release_revision_source is None:
            return self._validate_identity_and_collections()
        expected_revision = {
            "railway_commit_sha": self.release_revision,
            "local_development": "development",
            "unavailable": "unavailable",
        }[self.release_revision_source]
        if self.release_revision_source == "railway_commit_sha":
            if re.fullmatch(r"[a-f0-9]{40}", self.release_revision) is None:
                raise ValueError("Railway release provenance requires a commit SHA")
        elif self.release_revision != expected_revision:
            raise ValueError("release revision must match its closed provenance")
        return self._validate_identity_and_collections()

    def _validate_identity_and_collections(self) -> WorkflowAlertEnvelopeV1:
        if len(self.source_keys) != len(set(self.source_keys)):
            raise ValueError("workflow alert source_keys must be unique")
        if len(self.codes) != len(set(self.codes)):
            raise ValueError("workflow alert codes must be unique")

        path = self.diagnostic_url.path or ""
        if self.source_kind == "operation":
            if self.operation_id is None:
                raise ValueError("operation alerts require operation_id")
            if self.workflow_type == "content.reconciliation" or self.outcome == "reconciled":
                raise ValueError("operation alerts require an operation classification")
            expected_severity = "error" if self.outcome == "failed" else "warning"
            terminal_status = "failed" if self.outcome == "failed" else "completed"
            claim_generation = self.attempt - 1
            expected_event_key = (
                f"operation:{self.operation_id}:claim:{claim_generation}:status:{terminal_status}"
            )
            if self.severity != expected_severity or self.event_key != expected_event_key:
                raise ValueError(
                    "operation alert classification must match terminal claim identity"
                )
            if path != f"/api/v1/operations/{self.operation_id}":
                raise ValueError("operation diagnostic_url must match operation_id")
            return self

        if self.source_kind == "system_check":
            # A9 point 6. Without this branch a system_check alert falls through to
            # the reconciliation check below and raises on `workflow_type !=
            # "content.reconciliation"` — AFTER every other widening point is in
            # place. This branch asserts for system checks exactly what the other
            # branches assert for their kinds, so the widening is not merely
            # permissive.
            if self.operation_id is not None:
                raise ValueError("system check alerts must omit operation_id")
            if self.workflow_type != "system.backup_freshness":
                raise ValueError("system check alerts require a system workflow type")
            if self.attempt != 1:
                raise ValueError("system check alerts use immutable attempt 1")
            if re.fullmatch(SYSTEM_CHECK_EVENT_KEY_PATTERN, self.event_key) is None:
                raise ValueError("system check alert event_key has an invalid identity")
            if path != f"/api/v1/workflow-terminal-events/{self.event_id}":
                raise ValueError("system check diagnostic_url must match event_id")
            if self.outcome == "reconciled":
                raise ValueError("system check alerts are not reconciliation outcomes")
            return self

        if self.operation_id is not None or self.workflow_type != "content.reconciliation":
            raise ValueError("reconciliation alerts must omit operation_id and use workflow type")
        if self.attempt != 1:
            raise ValueError("reconciliation alerts use immutable attempt 1")
        expected_event_path = f"/api/v1/workflow-terminal-events/{self.event_id}"
        if path != expected_event_path:
            raise ValueError("reconciliation diagnostic_url must match event_id")

        if self.source_kind == "reconciliation_action":
            valid_key = re.fullmatch(r"reconciliation-action:[1-9][0-9]*", self.event_key)
            valid_classification = self.outcome == "reconciled" and self.severity == "warning"
        else:
            valid_key = re.fullmatch(
                r"reconciliation-failure:"
                r"[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-"
                r"[89ab][a-f0-9]{3}-[a-f0-9]{12}:"
                r"content:[1-9][0-9]*:reason:apply_failed",
                self.event_key,
            )
            valid_classification = self.outcome == "failed" and self.severity == "error"
        if valid_key is None or not valid_classification:
            raise ValueError("reconciliation alert classification must match source identity")
        return self


class WorkflowAlertDeliveryV1(StrictModel):
    """Bounded delivery state passed between the outbox repository and sink."""

    schema_version: Literal[1] = 1
    delivery_id: UUID
    event_id: UUID
    sink_name: Annotated[
        str,
        Field(min_length=1, max_length=64, pattern="^[a-z][a-z0-9_-]*$"),
    ]
    status: WorkflowAlertDeliveryStatus
    attempt_count: Annotated[int, Field(ge=0, le=2_147_483_647)]
    next_attempt_at: AwareDatetime
    lease_expires_at: AwareDatetime | None = None
    delivered_at: AwareDatetime | None = None
    last_error_code: str | None = Field(
        None,
        min_length=1,
        max_length=80,
        pattern="^[a-z][a-z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def validate_delivery_state(self) -> WorkflowAlertDeliveryV1:
        if self.status == "pending":
            if self.lease_expires_at is not None or self.delivered_at is not None:
                raise ValueError("pending delivery must not retain lease or delivery timestamps")
            return self
        if self.status == "leased":
            if (
                self.attempt_count < 1
                or self.lease_expires_at is None
                or self.delivered_at is not None
            ):
                raise ValueError("leased delivery requires an active attempted lease")
            return self
        if self.status == "delivered":
            if (
                self.attempt_count < 1
                or self.lease_expires_at is not None
                or self.delivered_at is None
                or self.last_error_code is not None
            ):
                raise ValueError("delivered state requires a clean completed attempt")
            return self
        if (
            self.attempt_count < 1
            or self.lease_expires_at is not None
            or self.delivered_at is not None
            or self.last_error_code is None
        ):
            raise ValueError("failed terminal delivery requires an attempted closed error")
        return self


class WorkflowAlertStagingRedactionAssertions(StrictModel):
    no_secrets: Literal[True]
    no_pii: Literal[True]
    no_user_content: Literal[True]
    no_raw_urls: Literal[True]
    schema_valid: Literal[True]


class WorkflowAlertStagingEvidenceV1(StrictModel):
    """Sanitized staging proof; request and response bodies are deliberately absent."""

    schema_version: Literal[1] = 1
    environment_class: Literal["staging"] = "staging"
    revision: Annotated[str, Field(min_length=40, max_length=40, pattern="^[a-f0-9]{40}$")]
    revision_source: Literal["railway_commit_sha"] = "railway_commit_sha"
    operation_id: BoundedPositiveIdentifier
    attempt: Annotated[int, Field(ge=1, le=2_147_483_648)]
    event_id: UUID
    outcome: Literal["partial", "zero_items", "failed", "unknown", "reconciled"]
    severity: WorkflowAlertExternalSeverity
    terminal_at: AwareDatetime
    received_at: AwareDatetime
    receipt_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    delivery_count: Literal[1]
    redaction_assertions: WorkflowAlertStagingRedactionAssertions

    @model_validator(mode="after")
    def validate_outcome_severity(self) -> WorkflowAlertStagingEvidenceV1:
        expected_severity = "error" if self.outcome == "failed" else "warning"
        if self.severity != expected_severity:
            raise ValueError("staging evidence severity must match its closed outcome")
        return self


def _is_canonical_uuid(value: str) -> bool:
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version in {1, 2, 3, 4, 5}
