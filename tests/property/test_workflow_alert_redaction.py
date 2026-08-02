from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from hypothesis import given, strategies as st

from src.services.workflow_terminal_event_service import (
    PersistedTerminalSnapshot,
    TerminalEventEvidence,
    classify_terminal_event,
    project_alert_envelope,
)


@given(
    hostile=st.one_of(
        st.emails(),
        st.from_regex(r"https://[^ ]{1,80}", fullmatch=True),
        st.sampled_from(
            [
                "sk-live-super-secret",
                "rss:https://private.example/feed?token=secret",
                "prompt: summarize my medical history",
            ]
        ),
    )
)
def test_allowlist_projection_never_exports_hostile_diagnostics_or_extensions(
    hostile: str,
) -> None:
    result = {
        "schema_version": 2,
        "command_key": "rss",
        "resolved_route": "rss",
        "emitted_sources": ["rss"],
        "status": "partial",
        "outcome": "partial",
        "items_ingested": 1,
        "items_skipped": 0,
        "items_failed": 1,
        "content_ids": [7],
        "errors": [{"code": "feed_ingest_error", "message": hostile}],
        "warnings": [{"code": hostile[:100] or "x", "message": hostile}],
        "errors_omitted": 0,
        "warnings_omitted": 0,
        "source_outcomes": [
            {
                "source_key": "src_0123456789abcdef0123",
                "status": "partial",
                "items_ingested": 1,
                "items_failed": 1,
                "errors": [],
                "warnings": [],
                "errors_omitted": 0,
                "warnings_omitted": 0,
            }
        ],
        "source_outcomes_omitted": 0,
        "details": {},
        "details_omitted": 0,
    }
    event = TerminalEventEvidence(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key="operation:42:claim:2:status:completed",
        source_kind="operation",
        operation_id=42,
        claim_generation=2,
        terminal_status="completed",
        reconciliation_action_id=None,
        reconciliation_run_id=None,
        reconciliation_content_id=None,
        occurred_at=datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
    )

    classification = classify_terminal_event(
        event,
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="completed",
            result=result,
        ),
    )
    envelope = project_alert_envelope(event, classification, "https://ops.example.com")
    serialized = json.dumps(envelope.model_dump(mode="json"), sort_keys=True)

    if hostile not in {
        "partial",
        "warning",
        "operation",
        "ingestion.execute",
        "feed_ingest_error",
    }:
        assert hostile not in serialized
    assert set(envelope.model_fields_set) == {
        "event_id",
        "event_key",
        "occurred_at",
        "severity",
        "outcome",
        "source_kind",
        "workflow_type",
        "operation_id",
        "attempt",
        "diagnostic_url",
        "resource_refs",
        "source_keys",
        "counts",
        "codes",
    }
