"""Closed contracts for durable workflow terminal events and external alerts."""

from __future__ import annotations

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

from src.contracts.workflow_models import StrictModel, TerminalOperationStatus

WorkflowTerminalOutcome = Literal[
    "success", "partial", "zero_items", "cancelled", "failed", "unknown", "reconciled"
]
WorkflowAlertSeverity = Literal["info", "warning", "error"]
WorkflowAlertExternalSeverity = Literal["warning", "error"]
WorkflowTerminalSourceKind = Literal["operation", "reconciliation_action", "reconciliation_failure"]
WorkflowAlertDeliveryStatus = Literal[
    "pending", "leased", "delivered", "permanent_failure", "exhausted"
]

BoundedPositiveIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=19, pattern="^[1-9][0-9]*$"),
]
WorkflowEventKey = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern="^[a-z0-9:_-]+$"),
]
WorkflowTypeName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern="^[a-z][a-z0-9_.-]*$"),
]
WorkflowDiagnosticUrl = Annotated[
    AnyUrl,
    UrlConstraints(max_length=2048, allowed_schemes=["https"]),
]


class WorkflowTerminalEventV1(StrictModel):
    """Minimal safe terminal intent read from the durable outbox."""

    schema_version: Literal[1] = 1
    event_id: UUID
    event_key: WorkflowEventKey
    source_kind: WorkflowTerminalSourceKind
    operation_id: BoundedPositiveIdentifier | None = None
    attempt: Annotated[int, Field(ge=1, le=2_147_483_647)]
    terminal_status: TerminalOperationStatus | None = None
    occurred_at: AwareDatetime


class WorkflowAlertResourceReference(StrictModel):
    type: Annotated[str, Field(min_length=1, max_length=40, pattern="^[a-z][a-z0-9_]*$")]
    id: Annotated[str, Field(min_length=1, max_length=80, pattern="^[A-Za-z0-9_-]+$")]


class WorkflowAlertCounts(StrictModel):
    items_ingested: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    items_skipped: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    items_failed: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    sources_total: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    sources_omitted: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    resources_omitted: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)
    codes_omitted: int | None = Field(None, ge=0, le=9_223_372_036_854_775_807)

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
    operation_id: BoundedPositiveIdentifier | None
    attempt: Annotated[int, Field(ge=1, le=2_147_483_647)]
    diagnostic_url: WorkflowDiagnosticUrl
    resource_refs: Annotated[list[WorkflowAlertResourceReference], Field(max_length=20)]
    source_keys: Annotated[
        list[Annotated[str, Field(pattern="^src_[a-f0-9]{20}$")]],
        Field(max_length=100),
    ]
    counts: WorkflowAlertCounts
    codes: Annotated[
        list[
            Annotated[
                str,
                Field(min_length=1, max_length=100, pattern="^[a-z][a-z0-9_.-]*$"),
            ]
        ],
        Field(max_length=20),
    ]

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
    def validate_unique_collections(self) -> WorkflowAlertEnvelopeV1:
        if len(self.source_keys) != len(set(self.source_keys)):
            raise ValueError("workflow alert source_keys must be unique")
        if len(self.codes) != len(set(self.codes)):
            raise ValueError("workflow alert codes must be unique")
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
    operation_id: BoundedPositiveIdentifier
    attempt: Annotated[int, Field(ge=1, le=2_147_483_647)]
    event_id: UUID
    outcome: Literal["partial", "zero_items", "failed", "unknown", "reconciled"]
    severity: WorkflowAlertExternalSeverity
    terminal_at: AwareDatetime
    received_at: AwareDatetime
    receipt_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    delivery_count: Literal[1]
    redaction_assertions: WorkflowAlertStagingRedactionAssertions


def _is_canonical_uuid(value: str) -> bool:
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version in {1, 2, 3, 4, 5}
