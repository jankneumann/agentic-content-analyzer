"""Tests for ``build_response_from_source_results``.

Pins the per-item failure aggregation contract that powers the harmonized
ingestion envelope: per-source ``items_failed`` / ``item_errors`` flow up,
plus an ``extra_*`` channel for service-level (cross-source) failures
like RSS persistence. Status derivation must treat ``items_failed`` as a
valid failure signal even when ``errors`` is empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.ingestion.result import (
    IngestionError,
    build_response_from_source_results,
)


@dataclass
class _StubSourceResult:
    """Mimics the duck-typed shape consumed by the helper."""

    url: str
    success: bool = True
    error: str | None = None
    error_type: str | None = None
    redirected_to: str | None = None
    items_failed: int = 0
    item_errors: list[IngestionError] = field(default_factory=list)


def test_per_source_items_failed_flows_into_envelope():
    sr = _StubSourceResult(
        url="https://example.com/feed",
        items_failed=2,
        item_errors=[
            IngestionError(code="parse_error", message="bad entry", url="https://x/1"),
            IngestionError(code="parse_error", message="bad entry", url="https://x/2"),
        ],
    )
    resp = build_response_from_source_results(
        command="ingest.rss",
        source="rss",
        items_ingested=3,
        source_results=[sr],
    )
    assert resp.items_ingested == 3
    assert resp.items_failed == 2
    assert resp.status == "partial"
    assert len(resp.errors) == 2
    assert {e.code for e in resp.errors} == {"parse_error"}


def test_extra_item_errors_aggregated_on_top_of_source_results():
    sr = _StubSourceResult(url="https://example.com/feed", items_failed=1)
    resp = build_response_from_source_results(
        command="ingest.rss",
        source="rss",
        items_ingested=4,
        source_results=[sr],
        extra_item_errors=[
            IngestionError(code="persistence_error", message="db err", url="https://x/3"),
        ],
        extra_items_failed=1,
    )
    assert resp.items_failed == 2
    assert resp.status == "partial"
    assert len(resp.errors) == 1
    assert resp.errors[0].code == "persistence_error"


def test_items_failed_only_yields_partial_when_some_landed():
    """The validator-loosening this builder relies on: items_failed without
    explicit errors[] entries still drives status='partial' / 'error'."""
    sr = _StubSourceResult(url="https://example.com/feed", items_failed=2)
    resp = build_response_from_source_results(
        command="ingest.rss",
        source="rss",
        items_ingested=1,
        source_results=[sr],
    )
    assert resp.status == "partial"
    assert resp.items_failed == 2
    assert resp.errors == []


def test_items_failed_only_yields_error_when_nothing_landed():
    sr = _StubSourceResult(url="https://example.com/feed", items_failed=3)
    resp = build_response_from_source_results(
        command="ingest.rss",
        source="rss",
        items_ingested=0,
        source_results=[sr],
    )
    assert resp.status == "error"
    assert resp.items_failed == 3


def test_zero_failures_yields_ok():
    sr = _StubSourceResult(url="https://example.com/feed")
    resp = build_response_from_source_results(
        command="ingest.rss",
        source="rss",
        items_ingested=5,
        source_results=[sr],
    )
    assert resp.status == "ok"
    assert resp.items_failed == 0


def test_legacy_source_result_without_new_fields_still_works():
    """Sources not yet migrated emit dataclasses missing items_failed /
    item_errors. The helper must tolerate them via getattr defaults."""

    @dataclass
    class _LegacyResult:
        url: str
        success: bool = True
        error: str | None = None
        error_type: str | None = None

    resp = build_response_from_source_results(
        command="ingest.blog",
        source="blog",
        items_ingested=2,
        source_results=[_LegacyResult(url="https://example.com")],
    )
    assert resp.status == "ok"
    assert resp.items_failed == 0


def test_source_level_error_combined_with_per_item_failures():
    """A source that hard-failed at fetch time AND a source where items
    failed mid-processing should both surface in errors[]."""
    failed_source = _StubSourceResult(
        url="https://broken.example",
        success=False,
        error="connection refused",
        error_type="ConnectError",
    )
    partial_source = _StubSourceResult(
        url="https://ok.example",
        items_failed=1,
        item_errors=[IngestionError(code="parse_error", message="bad", url="https://ok/1")],
    )
    resp = build_response_from_source_results(
        command="ingest.rss",
        source="rss",
        items_ingested=2,
        source_results=[failed_source, partial_source],
    )
    assert resp.status == "partial"
    assert resp.items_failed == 1
    codes = {e.code for e in resp.errors}
    assert codes == {"ConnectError", "parse_error"}
