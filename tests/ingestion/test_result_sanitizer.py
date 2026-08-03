from __future__ import annotations

import json

import pytest

from src.ingestion.result_sanitizer import (
    MAX_INGESTION_METADATA_BYTES,
    MAX_TOTAL_DIAGNOSTICS,
    SAFE_INGESTION_DIAGNOSTIC_CODES,
    sanitize_ingestion_diagnostic_code,
    sanitize_ingestion_metadata,
)

OBSIDIAN_DIAGNOSTIC_CODES = (
    "body_too_large",
    "directory_unavailable",
    "file_unavailable",
    "file_unstable",
    "frontmatter_not_mapping",
    "frontmatter_too_large",
    "generated_content",
    "invalid_capture_client",
    "invalid_captured_at",
    "invalid_content_type_hint",
    "invalid_cursor",
    "invalid_encoding",
    "invalid_frontmatter",
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
)


def test_diagnostic_codes_use_a_closed_public_vocabulary() -> None:
    assert sanitize_ingestion_diagnostic_code("fetch_error") == "fetch_error"
    assert sanitize_ingestion_diagnostic_code("sk-proj-private-token") == "unexpected_error"
    assert sanitize_ingestion_diagnostic_code("token_private_mailbox") == "unexpected_error"


@pytest.mark.parametrize("code", OBSIDIAN_DIAGNOSTIC_CODES)
def test_obsidian_diagnostic_codes_survive_with_generic_bounded_messages(code: str) -> None:
    secret = "DO-NOT-PERSIST"

    projection = sanitize_ingestion_metadata(
        errors=[
            {
                "code": code,
                "message": f"/srv/private/Vault/Inbox/note.md {secret}",
                "path": f"/srv/private/Vault/{secret}.md",
                "url": f"https://example.com/private?token={secret}",
                "body": f"private clip body {secret}",
                "frontmatter": {"source_url": secret},
            }
        ]
    )
    serialized = json.dumps(projection, sort_keys=True)

    assert code in SAFE_INGESTION_DIAGNOSTIC_CODES
    assert projection["errors"][0]["code"] == code
    assert 0 < len(projection["errors"][0]["message"]) <= 500
    assert secret not in serialized
    assert "/srv/private" not in serialized
    assert "example.com/private" not in serialized
    assert "private clip body" not in serialized
    assert "source_url" not in serialized


def test_sanitizer_removes_sensitive_and_log_forging_values() -> None:
    secret = "DO-NOT-PERSIST"
    projection = sanitize_ingestion_metadata(
        errors=[
            {
                "code": "feed_ingest_error",
                "message": (
                    "Fetch https://user:pass@example.com/private?"
                    f"token={secret} failed\nFORGED log line prompt={secret}"
                ),
                "url": f"https://example.com/private?api_key={secret}",
            }
        ],
        warnings=[
            {
                "code": "feed_redirected",
                "message": f"subject:{secret} redirected",
                "redirected_to": f"https://example.com/?credential={secret}",
                "redirected_source_key": "src_0123456789abcdefabcd",
            }
        ],
        details={
            "dry_run": True,
            "papers_ingested": 3,
            "query_echo": f"subject:{secret}",
            "citations": [f"https://example.com/?token={secret}"],
            "nested": {"prompt": secret},
        },
    )
    serialized = json.dumps(projection, sort_keys=True)

    assert secret not in serialized
    assert "user:pass" not in serialized
    assert "FORGED log line" not in serialized
    assert projection["errors"] == [
        {
            "code": "feed_ingest_error",
            "message": "A configured source could not be ingested",
        }
    ]
    assert projection["warnings"] == [
        {
            "code": "feed_redirected",
            "message": "A configured source redirected",
            "redirected_source_key": "src_0123456789abcdefabcd",
        }
    ]
    assert projection["details"] == {"dry_run": True, "papers_ingested": 3}
    assert projection["details_omitted"] == 3


def test_sanitizer_is_deterministic_and_enforces_global_budgets() -> None:
    diagnostics = [
        {
            "code": "parse_error",
            "message": f"private diagnostic {index}",
        }
        for index in range(40)
    ]
    source_outcomes = [
        {
            "source_key": f"src_{index:020x}",
            "status": "partial",
            "items_ingested": index,
            "items_failed": 1,
            "errors": list(reversed(diagnostics)),
            "warnings": diagnostics,
        }
        for index in range(120)
    ]

    forward = sanitize_ingestion_metadata(
        errors=diagnostics,
        warnings=list(reversed(diagnostics)),
        source_outcomes=source_outcomes,
        details={"papers_ingested": 4, "query_echo": "private"},
    )
    reversed_input = sanitize_ingestion_metadata(
        errors=list(reversed(diagnostics)),
        warnings=diagnostics,
        source_outcomes=list(reversed(source_outcomes)),
        details={"query_echo": "private", "papers_ingested": 4},
    )

    assert forward == reversed_input
    retained_diagnostics = (
        len(forward["errors"])
        + len(forward["warnings"])
        + sum(
            len(source["errors"]) + len(source["warnings"]) for source in forward["source_outcomes"]
        )
    )
    assert retained_diagnostics <= MAX_TOTAL_DIAGNOSTICS
    assert len(forward["source_outcomes"]) <= 100
    assert forward["source_outcomes_omitted"] >= 20
    assert len(json.dumps(forward, sort_keys=True).encode("utf-8")) <= MAX_INGESTION_METADATA_BYTES


def test_sanitizer_omits_invalid_source_identity_and_unsafe_detail_types() -> None:
    projection = sanitize_ingestion_metadata(
        source_outcomes=[
            {
                "source_key": "https://private.example/feed",
                "status": "error",
                "items_ingested": 0,
                "items_failed": 1,
            },
            {
                "source_key": "src_0123456789abcdefabcd",
                "status": "error",
                "items_ingested": 0,
                "items_failed": 1,
            },
        ],
        details={
            "dry_run": "true",
            "papers_ingested": -1,
            "citations_found": 4,
        },
    )

    assert [source["source_key"] for source in projection["source_outcomes"]] == [
        "src_0123456789abcdefabcd"
    ]
    assert projection["source_outcomes_omitted"] == 1
    assert projection["details"] == {"citations_found": 4}
    assert projection["details_omitted"] == 2
