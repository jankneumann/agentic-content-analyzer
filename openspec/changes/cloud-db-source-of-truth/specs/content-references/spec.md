# content-references Specification Delta

## ADDED Requirements

### Requirement: HTTP reference extraction endpoint

The system SHALL expose a `POST /api/v1/references/extract` endpoint that runs the reference extractor over a specified content batch (by IDs or date range) and stores extracted references. The endpoint MUST be tagged `@audited(operation="references.extract")`.

Input bounds (enforced by Pydantic validation, reflected in OpenAPI):

- Either `content_ids` (array of integers, 1 ≤ length ≤ 500) **XOR** the date range (`since` required, `until` optional — defaults to now) — the two inputs are mutually exclusive.
- `batch_size` (optional, default 50, max 500) caps how many content items are processed per call.
- Extraction runs entirely within one request; for date ranges that exceed `batch_size`, the response indicates `has_more: true` and the caller paginates by advancing `since` to the last-processed content's ingestion timestamp.

#### Scenario: Extract references for content batch by IDs

- **WHEN** a client sends `POST /api/v1/references/extract` with body `{"content_ids": [1, 2, 3]}` and a valid admin key
- **THEN** the API runs extraction and returns a 200 response with `references_extracted`, `content_processed`, `has_more: false`, and a `per_content` summary
- **AND** the audit log records the operation with `operation=references.extract`

#### Scenario: Extract references for content by date range (bounded batch)

- **WHEN** a client sends `POST /api/v1/references/extract` with body `{"since": "2026-04-01", "until": "2026-04-21", "batch_size": 50}`
- **THEN** the API processes up to 50 content items in the range and returns `content_processed <= 50`
- **AND** the response includes `has_more: true` if more items remain in the range and a `next_cursor` timestamp equal to the `ingested_at` of the last-processed item

#### Scenario: Extract references rejects conflicting filters

- **WHEN** the request includes both `content_ids` AND `since`/`until`
- **THEN** the API returns 422 Unprocessable Entity with a `Problem` body explaining that the fields are mutually exclusive

#### Scenario: Extract references rejects oversized content_ids

- **WHEN** a client sends `content_ids` with more than 500 elements
- **THEN** the API returns 422 with a `Problem` body naming the `content_ids` field and the maximum allowed length

### Requirement: HTTP reference resolution endpoint

The system SHALL expose a `POST /api/v1/references/resolve` endpoint that resolves a batch of extracted references against existing content (matching by external IDs, URLs, or DOIs). The endpoint MUST be tagged `@audited(operation="references.resolve")`.

Input bounds (enforced by Pydantic validation):

- `batch_size` (integer, 1 ≤ value ≤ 1000, default 100) — caps how many unresolved references are attempted per call.
- An empty body `{}` is valid and defaults `batch_size=100`.

#### Scenario: Resolve all unresolved references uses default batch

- **WHEN** a client sends `POST /api/v1/references/resolve` with body `{}` (no filters)
- **THEN** the API processes at most 100 unresolved references (the default batch_size)
- **AND** returns `resolved_count`, `still_unresolved_count`, and `has_more: true/false`
- **AND** the audit log records the operation with `operation=references.resolve`

#### Scenario: Resolve with explicit batch limit

- **WHEN** a client sends `POST /api/v1/references/resolve` with body `{"batch_size": 500}`
- **THEN** the API resolves at most 500 references in one call
- **AND** the response includes `has_more: true` when more unresolved references remain after the batch

#### Scenario: Resolve rejects oversized batch_size

- **WHEN** a client sends `{"batch_size": 5000}`
- **THEN** the API returns 422 with a `Problem` body naming the `batch_size` field and maximum 1000
