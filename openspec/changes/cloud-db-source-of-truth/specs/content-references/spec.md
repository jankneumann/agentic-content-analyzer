# content-references Specification Delta

## ADDED Requirements

### Requirement: HTTP reference extraction endpoint

The system SHALL expose a `POST /api/v1/references/extract` endpoint that runs the reference extractor over a specified content batch (by IDs or date range) and stores extracted references. The endpoint MUST be tagged `@audited`.

#### Scenario: Extract references for content batch by IDs

- **WHEN** a client sends `POST /api/v1/references/extract` with body `{"content_ids": [1, 2, 3]}` and a valid admin key
- **THEN** the API runs extraction and returns a 200 response with `references_extracted`, `content_processed`, and a per-content summary
- **AND** the audit log records the operation with `operation=references.extract`

#### Scenario: Extract references for content by date range

- **WHEN** a client sends `POST /api/v1/references/extract` with body `{"since": "2026-04-01", "until": "2026-04-21"}`
- **THEN** the API processes all content ingested in the range and returns aggregate counts

#### Scenario: Extract references rejects conflicting filters

- **WHEN** the request includes both `content_ids` and `since`/`until`
- **THEN** the API returns 422 Unprocessable Entity with a clear error message

### Requirement: HTTP reference resolution endpoint

The system SHALL expose a `POST /api/v1/references/resolve` endpoint that resolves a batch of extracted references against existing content (matching by external IDs, URLs, or DOIs). The endpoint MUST be tagged `@audited`.

#### Scenario: Resolve all unresolved references

- **WHEN** a client sends `POST /api/v1/references/resolve` with body `{}` (no filters)
- **THEN** the API processes all unresolved references and returns `resolved_count`, `still_unresolved_count`
- **AND** the audit log records the operation with `operation=references.resolve`

#### Scenario: Resolve with batch limit

- **WHEN** a client sends `POST /api/v1/references/resolve` with body `{"batch_size": 100}`
- **THEN** the API resolves at most 100 references per call
- **AND** the response includes `has_more: true/false` indicating whether another call would process additional references
