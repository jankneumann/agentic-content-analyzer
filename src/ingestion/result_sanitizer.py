"""Bounded, locator-free projection helpers for durable ingestion results."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

MAX_DIAGNOSTICS_PER_KIND = 20
MAX_TOTAL_DIAGNOSTICS = 20
MAX_SOURCE_OUTCOMES = 100
MAX_DIAGNOSTIC_MESSAGE_LENGTH = 500
MAX_INGESTION_METADATA_BYTES = 65_536
MAX_SAFE_COUNT = 9_007_199_254_740_991

_SOURCE_KEY_RE = re.compile(r"^src_[a-f0-9]{20}$")
_SAFE_DETAIL_FIELDS: dict[str, type] = {
    "dry_run": bool,
    "duplicate": bool,
    "version_updated": bool,
    "papers_ingested": int,
    "refs_ingested": int,
    "content_scanned": int,
    "references_found": int,
    "references_resolved": int,
    "references_unresolved": int,
    "queries_made": int,
    "citations_found": int,
    "tool_calls_made": int,
    "threads_found": int,
}
_SAFE_DIAGNOSTIC_MESSAGES = {
    "arxiv_paper_error": "An arXiv paper could not be ingested",
    "arxiv_source_error": "An arXiv source could not be ingested",
    "channel_ingest_error": "A configured channel could not be ingested",
    "channel_unresolvable": "A configured channel could not be resolved",
    "empty_response": "The source returned no content",
    "extraction_failed": "Content extraction failed",
    "feed_ingest_error": "A configured source could not be ingested",
    "feed_redirected": "A configured source redirected",
    "fetch_error": "A configured source could not be fetched",
    "file_ingest_error": "A file could not be ingested",
    "file_not_found": "A requested file was not found",
    "invalid_youtube_playlist": "The YouTube playlist is invalid",
    "invalid_youtube_url": "The YouTube URL is invalid",
    "oauth_unavailable": "Source authorization is unavailable",
    "parse_error": "A source item could not be parsed",
    "persistence_error": "A source item could not be persisted",
    "playlist_ingest_error": "A configured playlist could not be ingested",
    "scholar_paper_error": "A scholarly paper could not be ingested",
    "scholar_source_error": "A scholarly source could not be ingested",
    "search_failed": "The configured search failed",
    "storage_error": "A source item could not be stored",
    "unexpected_error": "The source reported an unexpected error",
    "video_processing_error": "A video could not be processed",
    "youtube_metadata_failed": "YouTube metadata could not be retrieved",
    "youtube_video_not_found": "The YouTube video was not found",
}


def sanitize_ingestion_metadata(
    *,
    errors: Iterable[object] = (),
    warnings: Iterable[object] = (),
    source_outcomes: Iterable[Mapping[str, Any]] = (),
    source_outcomes_omitted: int = 0,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic, bounded metadata safe for a durable public result."""

    remaining_diagnostics = MAX_TOTAL_DIAGNOSTICS
    sanitized_errors, errors_omitted, remaining_diagnostics = _sanitize_diagnostics(
        errors,
        remaining=remaining_diagnostics,
    )
    sanitized_warnings, warnings_omitted, remaining_diagnostics = _sanitize_diagnostics(
        warnings,
        remaining=remaining_diagnostics,
    )

    raw_source_outcomes = sorted(
        (dict(value) for value in source_outcomes),
        key=lambda value: str(value.get("source_key", "")),
    )
    sanitized_sources: list[dict[str, Any]] = []
    source_outcomes_omitted = _safe_count(source_outcomes_omitted)
    for raw in raw_source_outcomes:
        if len(sanitized_sources) >= MAX_SOURCE_OUTCOMES:
            source_outcomes_omitted += 1
            continue
        source_key = raw.get("source_key")
        status = raw.get("status")
        if not isinstance(source_key, str) or not _SOURCE_KEY_RE.fullmatch(source_key):
            source_outcomes_omitted += 1
            continue
        if status not in {"ok", "partial", "error"}:
            source_outcomes_omitted += 1
            continue

        source_errors, source_errors_omitted, remaining_diagnostics = _sanitize_diagnostics(
            raw.get("errors", ()),
            remaining=remaining_diagnostics,
            already_omitted=_safe_count(raw.get("errors_omitted")),
        )
        source_warnings, source_warnings_omitted, remaining_diagnostics = _sanitize_diagnostics(
            raw.get("warnings", ()),
            remaining=remaining_diagnostics,
            already_omitted=_safe_count(raw.get("warnings_omitted")),
        )
        sanitized_sources.append(
            {
                "source_key": source_key,
                "status": status,
                "items_ingested": _safe_count(raw.get("items_ingested")),
                "items_failed": _safe_count(raw.get("items_failed")),
                "errors": source_errors,
                "warnings": source_warnings,
                "errors_omitted": source_errors_omitted,
                "warnings_omitted": source_warnings_omitted,
            }
        )

    safe_details, details_omitted = _sanitize_details(details or {})
    projection = {
        "errors": sanitized_errors,
        "warnings": sanitized_warnings,
        "errors_omitted": errors_omitted,
        "warnings_omitted": warnings_omitted,
        "source_outcomes": sanitized_sources,
        "source_outcomes_omitted": source_outcomes_omitted,
        "details": safe_details,
        "details_omitted": details_omitted,
    }
    _enforce_serialized_budget(projection)
    return projection


def _sanitize_diagnostics(
    entries: Iterable[object] | None,
    *,
    remaining: int,
    already_omitted: int = 0,
) -> tuple[list[dict[str, Any]], int, int]:
    raw_entries = list(entries or ())
    sanitized = sorted(
        (_sanitize_diagnostic(value) for value in raw_entries),
        key=lambda value: (
            value["code"],
            value["message"],
            value.get("redirected_source_key", ""),
        ),
    )
    keep = min(MAX_DIAGNOSTICS_PER_KIND, remaining, len(sanitized))
    omitted = min(MAX_SAFE_COUNT, already_omitted + len(sanitized) - keep)
    return sanitized[:keep], omitted, remaining - keep


def _sanitize_diagnostic(value: object) -> dict[str, Any]:
    raw = _as_mapping(value)
    raw_code = raw.get("code")
    code = raw_code if isinstance(raw_code, str) else ""
    if code not in _SAFE_DIAGNOSTIC_MESSAGES:
        code = "unexpected_error"
    result: dict[str, Any] = {
        "code": code,
        "message": _SAFE_DIAGNOSTIC_MESSAGES[code][:MAX_DIAGNOSTIC_MESSAGE_LENGTH],
    }
    redirected_source_key = raw.get("redirected_source_key")
    if isinstance(redirected_source_key, str) and _SOURCE_KEY_RE.fullmatch(redirected_source_key):
        result["redirected_source_key"] = redirected_source_key
    return result


def _sanitize_details(details: Mapping[str, Any]) -> tuple[dict[str, bool | int], int]:
    safe: dict[str, bool | int] = {}
    for key in sorted(details):
        value = details[key]
        expected = _SAFE_DETAIL_FIELDS.get(key)
        is_safe_value = (expected is bool and isinstance(value, bool)) or (
            expected is int
            and isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= MAX_SAFE_COUNT
        )
        if is_safe_value:
            safe[key] = value
    return safe, len(details) - len(safe)


def _safe_count(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return min(value, MAX_SAFE_COUNT)
    return 0


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dumped
    return {}


def _serialized_size(value: Mapping[str, Any]) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _enforce_serialized_budget(projection: dict[str, Any]) -> None:
    while (
        projection["source_outcomes"]
        and _serialized_size(projection) > MAX_INGESTION_METADATA_BYTES
    ):
        projection["source_outcomes"].pop()
        projection["source_outcomes_omitted"] += 1
    if _serialized_size(projection) > MAX_INGESTION_METADATA_BYTES:
        projection["details_omitted"] += len(projection["details"])
        projection["details"] = {}
    for key, omitted_key in (
        ("warnings", "warnings_omitted"),
        ("errors", "errors_omitted"),
    ):
        while projection[key] and _serialized_size(projection) > MAX_INGESTION_METADATA_BYTES:
            projection[key].pop()
            projection[omitted_key] += 1
    if _serialized_size(projection) > MAX_INGESTION_METADATA_BYTES:
        raise ValueError("sanitized ingestion metadata exceeds its serialized byte budget")
