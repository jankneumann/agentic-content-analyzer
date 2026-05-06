# Content References Specification

## Purpose

Cross-cutting content relationship tracking with dual PostgreSQL/Neo4j storage, background resolution, and optional auto-ingestion of referenced content.

## Requirements

### Requirement: Content References Table

The system MUST store content references in a `content_references` PostgreSQL table with:
- `source_content_id` (FK to contents.id) — the content item that contains the reference
- `reference_type` (ReferenceType enum) — relationship kind: cites, extends, discusses, contradicts, supplements
- `target_content_id` (FK to contents.id, nullable) — resolved target in DB
- `external_url` (text, nullable) — raw URL of the reference
- `external_id` (text, nullable) — structured identifier (arXiv ID, DOI, S2 ID)
- `external_id_type` (ExternalIdType enum, nullable) — identifier namespace
- `resolution_status` (ResolutionStatus enum) — unresolved, resolved, external, failed, not_found
- `resolved_at` (timestamp, nullable)
- `source_chunk_id` (FK to document_chunks.id, nullable) — chunk where reference was found, anchoring to the hierarchical document model
- `context_snippet` (text, nullable) — surrounding text (fallback when chunk not yet indexed)
- `confidence` (float, default 1.0) — extraction confidence score

The table MUST have a CHECK constraint: `CHECK (external_id IS NOT NULL OR external_url IS NOT NULL)` — every reference must have at least one identifier.

The URL uniqueness constraint MUST be a partial unique index (not a table constraint): `CREATE UNIQUE INDEX uq_content_reference_url ON content_references (source_content_id, external_url) WHERE external_id IS NULL`.

When `DocumentChunk` records exist for the source content, references MUST be anchored via `source_chunk_id` using chunk_index-based sequential matching (approximate character range from cumulative chunk text lengths). Note: `DocumentChunk.start_char`/`end_char` fields are not populated by current chunking strategies. When chunks are not yet available (content ingested but not yet chunked), `context_snippet` serves as fallback. References MUST be retroactively re-anchored when chunks are created or re-indexed for a content item.

#### Scenario: Store extracted reference with identifier

- **WHEN** reference extraction finds an external URL or structured identifier in a source content item
- **THEN** the system stores a `content_references` row linked to the source content
- **AND** the row contains at least one identifier (`external_id` or `external_url`)

### Requirement: Reference Extraction from Content

On content ingestion, the system MUST scan `markdown_content` and `links_json` for:
- arXiv IDs: `arXiv:YYMM.NNNNN`, `arxiv.org/abs/YYMM.NNNNN`, `arxiv.org/pdf/YYMM.NNNNN`
- DOIs: `doi.org/10.xxx`, `DOI: 10.xxx`
- Semantic Scholar URLs: `semanticscholar.org/paper/.../HASH`
- Internal content URLs (matching the application's own URL patterns)
- Generic URLs from `links_json` (lower confidence)

Extracted identifiers MUST be normalized (strip version suffixes, lowercase DOIs, remove URL prefixes).

Reference storage MUST use `INSERT ... ON CONFLICT DO NOTHING` (not session-level dedup) to handle duplicates atomically. This avoids the `autoflush=False` gotcha where newly added rows within the same batch are invisible to subsequent dedup checks.

#### Scenario: Extract normalized arXiv reference from markdown

- **WHEN** ingested markdown contains an arXiv URL or ID
- **THEN** reference extraction normalizes the identifier
- **AND** storage uses conflict-safe insertion so duplicate references do not create duplicate rows

### Requirement: Background Resolution

The system MUST provide a queue-based background job (`resolve_references`) that:
- Queries unresolved `content_references` rows
- Attempts resolution via GIN-indexed `metadata_json` containment queries
- Attempts resolution via `source_url` matching
- Updates `resolution_status`, `target_content_id`, and `resolved_at` on success
- Processes in configurable batch sizes (default 100)

#### Scenario: Resolve unresolved reference against existing content

- **WHEN** a background resolution job finds an unresolved reference matching existing content metadata or source URL
- **THEN** the system sets `target_content_id`, updates `resolution_status`, and records `resolved_at`

### Requirement: Reverse Resolution on Ingestion

When new content is ingested, the system MUST check for existing unresolved references that match:
- The new content's `arxiv_id` in `metadata_json`
- The new content's `doi` in `metadata_json`
- The new content's `source_url`

Matching references MUST be automatically resolved (set `target_content_id`, update status).

#### Scenario: New content resolves existing reference

- **WHEN** newly ingested content contains metadata or a source URL matching an existing unresolved reference
- **THEN** the system resolves that reference to the new content item

### Requirement: Neo4j Citation Edge Projection

Resolved references MUST be projected to Neo4j as edges:
- Edge type: `CITES` (from source Episode to target Episode)
- Edge properties: `reference_type`, `confidence`, `synced_at`
- Only resolved references with both `source_content_id` and `target_content_id` are synced
- Sync is one-way (PG → Neo4j), fire-and-forget, failure-safe

#### Scenario: Sync resolved reference to graph edge

- **WHEN** a reference has both source and target content IDs
- **THEN** the system projects it to Neo4j as a `CITES` edge with reference metadata
- **AND** graph sync failure does not block PostgreSQL persistence

### Requirement: Auto-Ingest Trigger (Optional)

When enabled via `reference_auto_ingest_enabled` setting, the system SHALL trigger bounded reference auto-ingest:
- Unresolved references with structured IDs (arXiv, DOI) trigger content ingestion
- arXiv IDs trigger `ingest_arxiv_paper()`
- DOIs trigger `ingest_scholar_paper()`
- Depth tracking via `metadata_json.auto_ingest_depth` integer: 0 for user-ingested, 1 for first-level auto-ingest, etc. Content with `auto_ingest_depth >= max_depth` does not trigger further auto-ingestion
- Auto-ingested content is tagged with both `ingestion_mode: "auto_ingest"` and `auto_ingest_depth: N` in metadata_json

#### Scenario: Auto-ingest structured unresolved reference

- **WHEN** auto-ingest is enabled and an unresolved reference has a supported structured identifier
- **THEN** the system triggers the matching ingestion path while respecting maximum depth limits

### Requirement: Supplementary Links (Scholar ↔ arXiv)

When both a Scholar abstract and an arXiv full-text record exist for the same paper, the system SHALL create supplementary links:
- Create **two** `supplements` reference rows (one in each direction: Scholar→arXiv and arXiv→Scholar) for true bidirectionality — avoids requiring symmetric query logic
- Detection via shared `arxiv_id` in `metadata_json`
- Created during ingestion of whichever record arrives second

#### Scenario: Link Scholar abstract and arXiv full text

- **WHEN** Scholar and arXiv records for the same paper both exist
- **THEN** the system creates bidirectional `supplements` reference rows

### Requirement: API Endpoints

The system SHALL expose HTTP endpoints for outgoing and incoming content-reference queries.

- `GET /api/v1/contents/{id}/references` — list references FROM this content (outgoing citations)
- `GET /api/v1/contents/{id}/cited-by` — list references TO this content (incoming citations)
- Response includes: reference_type, resolution_status, target content summary (if resolved), external_url/id (if unresolved)

#### Scenario: Query outgoing and incoming references

- **WHEN** a client requests references for a content item
- **THEN** the API returns outgoing and incoming reference details, including resolved target summaries when available

### Requirement: CLI Commands

The system SHALL expose CLI commands for reference extraction and resolution backfills.

- `aca manage extract-refs` — backfill references for existing content
  - Options: `--after DATE`, `--before DATE`, `--source SOURCE_TYPE`, `--dry-run`, `--batch-size N`
- `aca manage resolve-refs` — manually trigger resolution pass
  - Options: `--batch-size N`, `--auto-ingest`

#### Scenario: Run reference backfill from CLI

- **WHEN** an operator runs the reference extraction or resolution CLI command
- **THEN** the system processes the selected content or reference batch using the configured bounds and options

### Requirement: Database Migration

The system SHALL provide a database migration for content-reference storage, constraints, and supporting indexes.

- Create `content_references` table with indexes and CHECK constraint (`chk_has_identifier`)
- Use `VARCHAR(20)` columns with application-level `StrEnum` validation for `reference_type`, `external_id_type`, and `resolution_status` — do NOT create PostgreSQL enum types (avoids `ALTER TYPE ... ADD VALUE` migration burden per CLAUDE.md gotcha)
- Create partial unique index `uq_content_reference_url` using `CREATE UNIQUE INDEX ... WHERE external_id IS NULL` (not a table-level UNIQUE constraint, which does not support WHERE clauses)
- ALTER `contents.metadata_json` from `json` to `jsonb` if not already `jsonb`: `ALTER TABLE contents ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb` (required for GIN index and `@>` containment queries; coordinate with arXiv migration so only the first migration performs the ALTER)
- Create GIN index on `contents.metadata_json` if not already present (idempotent with `CREATE INDEX IF NOT EXISTS`)

#### Scenario: Apply content references migration

- **WHEN** migrations are applied to a database without content-reference storage
- **THEN** the system creates the table, constraints, and indexes needed for extraction and resolution

### Requirement: Settings

The system SHALL provide settings that control reference extraction, auto-ingest, graph sync, and confidence thresholds.

- `reference_extraction_enabled: bool = True` — enable/disable extraction on ingestion
- `reference_auto_ingest_enabled: bool = False` — enable/disable auto-ingest of unresolved refs
- `reference_auto_ingest_max_depth: int = 1` — prevent recursive auto-ingest
- `reference_neo4j_sync_enabled: bool = True` — enable/disable Neo4j projection
- `reference_min_confidence: float = 0.5` — minimum confidence to store a reference

#### Scenario: Configure reference automation

- **WHEN** reference settings are loaded
- **THEN** the system uses them to enable or disable extraction, auto-ingest, graph sync, and minimum-confidence filtering

### Requirement: Ingestion Hook

All ingestion services MUST call reference extraction after creating/updating a Content record:
- Extract references from the new content
- Store as `content_references` rows
- Enqueue `resolve_references` background job
- Call reverse resolution to update any existing unresolved refs pointing to the new content
- This hook MUST be fail-safe: reference extraction failure must not block content ingestion

#### Scenario: Ingestion triggers fail-safe reference hook

- **WHEN** an ingestion service creates or updates a content record
- **THEN** the system runs reference extraction and reverse resolution hooks
- **AND** hook failure does not block the content ingestion result

### Requirement: MCP Tool Surface

All API endpoints and CLI commands MUST also be registered as MCP tools in `src/mcp_server.py` via `@mcp.tool()`, following the existing delegation pattern:
- `get_content_references(content_id, direction)` — query outgoing/incoming references
- `extract_references(after, before, source, dry_run, batch_size)` — backfill extraction
- `resolve_references(batch_size, auto_ingest)` — trigger resolution pass
- `ingest_reference(reference_id)` — ad-hoc ingest for a specific unresolved reference. This tool operates **independently** of `reference_auto_ingest_enabled` — it requires explicit per-reference invocation and is not gated by the auto-ingest setting. The setting controls only unattended background auto-ingestion (REQ-REF-006).

This ensures agentic workflows (MCP clients, AI assistants) have the same citation discovery and ingestion capabilities as the API and CLI.

#### Scenario: MCP client invokes reference tool

- **WHEN** an MCP client invokes a content-reference tool
- **THEN** the system exposes the same citation discovery and ingestion capability as the API and CLI surfaces

### Requirement: HTTP reference extraction endpoint

The system SHALL expose a `POST /api/v1/references/extract` endpoint that runs the reference extractor over a specified content batch (by IDs or date range) and stores extracted references. The endpoint MUST be tagged `@audited(operation="references.extract")`.

Input bounds (enforced by Pydantic validation, reflected in OpenAPI):

- Either `content_ids` (array of integers, 1 ≤ length ≤ 500) **XOR** the date range (`since` required, `until` optional — defaults to now) — the two inputs are mutually exclusive.
- `batch_size` (optional, default 50, max 500) caps how many content items are processed per call.
- Extraction runs entirely within one request; for date ranges that exceed `batch_size`, the response indicates `has_more: true` and the caller paginates by passing `next_cursor` as `since` on the next call. `next_cursor` is the `ingested_at` of the **first unprocessed item** (the one immediately after the batch boundary). The server's filter is `ingested_at >= since`, so using the first-unprocessed timestamp resumes exactly where the previous call stopped without re-processing the last-processed row.

The response body matches `ReferencesExtractResponse` in `contracts/openapi/v1.yaml`:
- `references_extracted` (int, required)
- `content_processed` (int, required)
- `has_more` (bool, required)
- `next_cursor` (ISO-8601 date-time, optional) — present when `has_more=true` only
- `per_content` (array of `{content_id, references_found}`, optional) — included as an enriched detail when the batch size is small enough to afford the payload overhead; may be omitted on very large batches

Timeout: the endpoint SHALL respect a 60-second per-batch timeout. Requests exceeding the timeout return `504 Gateway Timeout` with a Problem body identifying the timeout source.

#### Scenario: Extract references for content batch by IDs

- **WHEN** a client sends `POST /api/v1/references/extract` with body `{"content_ids": [1, 2, 3]}` and a valid admin key
- **THEN** the API runs extraction and returns a 200 response with `references_extracted`, `content_processed`, `has_more: false`, and optionally a `per_content` summary
- **AND** `next_cursor` is absent (because `has_more=false`)
- **AND** the audit log records the operation with `operation=references.extract`

#### Scenario: Extract references for content by date range (bounded batch)

- **WHEN** a client sends `POST /api/v1/references/extract` with body `{"since": "2026-04-01", "until": "2026-04-21", "batch_size": 50}`
- **THEN** the API processes up to 50 content items in the range and returns `content_processed <= 50`
- **AND** the response includes `has_more: true` if more items remain in the range and a `next_cursor` timestamp equal to the `ingested_at` of the **first unprocessed item** (the row immediately after the batch boundary — passing this value as `since` on the next call resumes without re-processing the last-processed row, since the server uses `ingested_at >= since`)

#### Scenario: Extract references rejects conflicting filters

- **WHEN** the request includes both `content_ids` AND `since`/`until`
- **THEN** the API returns 422 Unprocessable Entity with a `Problem` body explaining that the fields are mutually exclusive

#### Scenario: Extract references rejects oversized content_ids

- **WHEN** a client sends `content_ids` with more than 500 elements
- **THEN** the API returns 422 with a `Problem` body naming the `content_ids` field and the maximum allowed length

#### Scenario: Extract references returns 504 on per-batch timeout

- **WHEN** extraction of the requested batch exceeds 60 seconds
- **THEN** the API returns 504 Gateway Timeout with a Problem body identifying the timeout
- **AND** the audit log still records the attempt with `status_code=504`

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

#### Scenario: Resolve returns 504 on per-batch timeout

- **WHEN** resolution of the requested batch exceeds 60 seconds
- **THEN** the API returns 504 Gateway Timeout with a Problem body identifying the timeout
- **AND** the audit log still records the attempt with `status_code=504`

## Scenarios

### Scenario: Blog post references arXiv paper (paper not in DB)
```
GIVEN a Substack blog post is ingested with markdown containing "arxiv.org/abs/2301.12345"
WHEN reference extraction runs
THEN a content_references row is created with:
  - source_content_id = blog.id
  - external_id = "2301.12345"
  - external_id_type = "arxiv"
  - external_url = "https://arxiv.org/abs/2301.12345"
  - resolution_status = "unresolved"
  - confidence = 1.0
```

### Scenario: arXiv paper later ingested, reference auto-resolves
```
GIVEN an unresolved content_reference exists with external_id="2301.12345", external_id_type="arxiv"
WHEN arXiv paper 2301.12345 is ingested with metadata_json.arxiv_id="2301.12345"
THEN reverse resolution matches the existing reference
AND sets target_content_id = arxiv_paper.id
AND sets resolution_status = "resolved"
AND sets resolved_at = now()
AND syncs a CITES edge to Neo4j
```

### Scenario: Auto-ingest triggered for unresolved DOI
```
GIVEN reference_auto_ingest_enabled = true
AND an unresolved reference exists with external_id="10.1234/paper", external_id_type="doi"
WHEN the resolve_references background job runs
THEN it calls ingest_scholar_paper("DOI:10.1234/paper")
AND the newly ingested content resolves the reference
AND the auto-ingested content has metadata_json.ingestion_mode = "auto_ingest"
AND the auto-ingested content has metadata_json.auto_ingest_depth = 1
```

### Scenario: Auto-ingest depth limit
```
GIVEN content A was auto-ingested (metadata_json.auto_ingest_depth = 1)
AND reference_auto_ingest_max_depth = 1
AND content A contains a reference to arXiv paper 2402.99999
WHEN reference extraction runs on content A
THEN the reference is extracted and stored as unresolved
BUT auto-ingest is NOT triggered (auto_ingest_depth >= max_depth)
```

### Scenario: Scholar and arXiv records linked as supplements
```
GIVEN a Scholar content record exists with metadata_json.arxiv_id = "2301.12345"
WHEN an arXiv content record is ingested for paper 2301.12345
THEN two content_references rows are created:
  - Row 1: source_content_id=scholar.id, target_content_id=arxiv.id, reference_type="supplements"
  - Row 2: source_content_id=arxiv.id, target_content_id=scholar.id, reference_type="supplements"
AND both have resolution_status = "resolved"
```

### Scenario: Generic URL reference from blog post
```
GIVEN a blog post links to "https://example.com/some-article" (no structured ID)
WHEN reference extraction runs
THEN a content_references row is created with:
  - external_url = "https://example.com/some-article"
  - external_id = NULL
  - external_id_type = NULL
  - confidence = 0.5
  - resolution_status = "unresolved"
```

### Scenario: Reference extraction is fail-safe
```
GIVEN reference extraction encounters a regex error or database error mid-way through processing
WHEN the extraction hook runs during content ingestion
THEN the error is logged at WARNING level
AND partial results (references successfully extracted before the error) are persisted
AND the content ingestion completes successfully (not blocked)
AND no automatic retry is attempted
```

### Scenario: API returns references for content item
```
GIVEN content A has 3 resolved references and 2 unresolved references
WHEN GET /api/v1/contents/{A.id}/references is called
THEN the response contains 5 reference objects
AND resolved references include target content title, source_type, and URL
AND unresolved references include external_id, external_url, and resolution_status
```

### Scenario: Backfill references for existing content
```
GIVEN 500 content items exist without extracted references
WHEN aca manage extract-refs --after 2025-01-01 --batch-size 50 runs
THEN references are extracted for matching content items in batches of 50
AND resolve_references jobs are enqueued for each batch
AND progress is logged (e.g., "Processed 50/500, extracted 127 references")
```

### Scenario: Re-ingested content preserves existing references
```
GIVEN content A has 3 extracted references in content_references
WHEN content A is re-ingested with force-reprocess
AND reference extraction runs again on the updated content
THEN existing references are preserved (INSERT ON CONFLICT DO NOTHING)
AND newly discovered references (from updated markdown) are added
AND stale references (from old content no longer present) are NOT deleted
```

### Scenario: Content with empty markdown_content
```
GIVEN a content item has markdown_content = NULL (e.g., failed PDF extraction)
WHEN reference extraction runs
THEN extract_from_content returns an empty list
AND no content_references rows are created
AND no error is raised
```

### Scenario: Neo4j unreachable during citation sync
```
GIVEN a reference is resolved (target_content_id set, status = "resolved")
AND Neo4j is unreachable (connection refused or timeout)
WHEN citation edge sync runs
THEN the error is logged at WARNING level
AND no exception propagates to the caller
AND the reference's PostgreSQL state is unchanged (still resolved)
AND no retry is enqueued (eventual consistency via next sync pass)
```
