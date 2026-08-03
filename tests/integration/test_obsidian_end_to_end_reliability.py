"""End-to-end reliability guards for Obsidian vault ingestion (task 6.2).

Covers the two boundaries the adapter, claim, and fixture suites do not reach:
what a clipped vault note becomes when it is *rendered*, and what a terminal
Obsidian operation becomes when it is *alerted on*. Both are places where vault
content or vault location could escape the worker.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from src.api.shared_routes import _md_to_html
from src.ingestion.obsidian_parser import parse_obsidian_clip
from src.services.workflow_terminal_event_service import (
    PersistedTerminalSnapshot,
    TerminalEventEvidence,
    classify_terminal_event,
    project_alert_envelope,
)

VAULT_PATH = "/srv/obsidian/personal"
NOTE_NAME = "quarterly-review.md"
FULL_URL = "https://private.example/report?token=secret-token"


def _clip(body: str) -> bytes:
    return (
        "---\n"
        f"source_url: {FULL_URL}\n"
        "captured_at: 2026-08-02T11:00:00Z\n"
        "capture_client: obsidian-web-clipper\n"
        "content_type_hint: article\n"
        "---\n"
        f"{body}\n"
    ).encode()


def test_hostile_clip_body_is_inert_after_normalization_and_rendering() -> None:
    """A clip is untrusted input; nothing in it may execute when rendered."""

    parsed = parse_obsidian_clip(
        _clip(
            "<script>alert('xss')</script>\n\n"
            "[click me](javascript:alert('xss'))\n\n"
            "[data](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)\n\n"
            "<img src=x onerror=alert('xss')>\n"
        )
    )
    rendered = _md_to_html(parsed.markdown)

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert 'href="javascript:' not in rendered
    assert 'href="data:' not in rendered
    # The img tag survives only as escaped text, never as an element that could
    # fire its handler.
    assert "<img" not in rendered
    assert "&lt;img src=x onerror=" in rendered


def test_obsidian_syntax_is_flattened_and_never_resolves_against_a_vault() -> None:
    """Wikilinks and embeds must not survive as links the renderer can follow."""

    parsed = parse_obsidian_clip(
        _clip(
            "[[Private Note]]\n\n"
            "[[Private Note|public alias]]\n\n"
            "![[Secret Attachment.png]]\n\n"
            "> [!warning] Callout title\n"
            "> body\n\n"
            "`[[Code Span Wikilink]]`\n"
        )
    )
    rendered = _md_to_html(parsed.markdown)

    # The vault-relative target never becomes a link target.
    assert 'href="Private Note' not in rendered
    assert 'src="Secret Attachment.png"' not in rendered
    # Content inside a code span is left exactly as the author wrote it.
    assert "[[Code Span Wikilink]]" in parsed.markdown


def _obsidian_result(
    *,
    outcome: str,
    status: str,
    items_ingested: int,
    items_skipped: int,
    items_failed: int,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, object]:
    """The exact durable result shape a real Obsidian scan terminates with."""

    return {
        "schema_version": 2,
        "command_key": "obsidian_vault",
        "resolved_route": "obsidian_vault",
        "emitted_sources": ["obsidian"],
        "status": status,
        "outcome": outcome,
        "items_ingested": items_ingested,
        "items_skipped": items_skipped,
        "items_failed": items_failed,
        "content_ids": [],
        "errors": errors,
        "warnings": warnings,
        "errors_omitted": 0,
        "warnings_omitted": 0,
        "source_outcomes": [
            {
                "source_key": "src_0123456789abcdef0123",
                "status": status,
                "items_ingested": items_ingested,
                "items_failed": items_failed,
                "errors": errors,
                "warnings": warnings,
                "errors_omitted": 0,
                "warnings_omitted": 0,
            }
        ],
        "source_outcomes_omitted": 0,
        "details": {},
        "details_omitted": 0,
    }


def _evidence(terminal_status: str) -> TerminalEventEvidence:
    return TerminalEventEvidence(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key=f"operation:91:claim:1:status:{terminal_status}",
        source_kind="operation",
        operation_id=91,
        claim_generation=1,
        terminal_status=terminal_status,
        reconciliation_action_id=None,
        reconciliation_run_id=None,
        reconciliation_content_id=None,
        occurred_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )


def test_converged_scan_of_an_unchanged_vault_is_a_zero_item_terminal_event() -> None:
    """The steady state of a polled vault must classify as zero_items, not failed.

    Once a permanently invalid note has spent its retry budget, later scans
    attempt nothing. The retained code stays in the result as a warning, and the
    operation is a successful terminal event.
    """

    classification = classify_terminal_event(
        _evidence("completed"),
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="completed",
            result=_obsidian_result(
                outcome="zero_items",
                status="ok",
                items_ingested=0,
                items_skipped=4,
                items_failed=0,
                errors=[],
                warnings=[{"code": "retry_exhausted", "message": "retained"}],
            ),
        ),
    )

    assert classification.workflow_type == "ingestion.execute"
    assert classification.outcome == "zero_items"


def test_obsidian_failure_alert_carries_codes_but_no_vault_location_or_url() -> None:
    """An externally routed Obsidian alert must leak neither path nor full URL."""

    event = _evidence("completed")
    classification = classify_terminal_event(
        event,
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="completed",
            result=_obsidian_result(
                outcome="partial",
                status="partial",
                items_ingested=2,
                items_skipped=1,
                items_failed=1,
                errors=[
                    {
                        "code": "missing_required_metadata",
                        "message": f"{VAULT_PATH}/Clips/{NOTE_NAME} -> {FULL_URL}",
                    }
                ],
                warnings=[],
            ),
        ),
    )
    envelope = project_alert_envelope(event, classification, "https://ops.example.com")
    serialized = json.dumps(envelope.model_dump(mode="json"), sort_keys=True)

    # The stable code survives, so the alert stays actionable...
    assert "missing_required_metadata" in serialized
    # ...but nothing identifying the vault, the note, or the clipped page does.
    for private_value in (VAULT_PATH, NOTE_NAME, FULL_URL, "secret-token", "private.example"):
        assert private_value not in serialized
    # The alert still points an operator at the durable operation.
    assert str(event.operation_id) in serialized
