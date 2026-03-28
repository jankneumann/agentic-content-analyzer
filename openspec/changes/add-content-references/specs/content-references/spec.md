# Content References Specification

## Overview

Cross-cutting content relationship tracking with dual PostgreSQL/Neo4j storage, background resolution, and optional auto-ingestion of referenced content.

## Requirements

### REQ-REF-001: Content References Table

The system must store content references in a `content_references` PostgreSQL table with:
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

When `DocumentChunk` records exist for the source content, references must be anchored via `source_chunk_id` using chunk_index-based sequential matching (approximate character range from cumulative chunk text lengths). Note: `DocumentChunk.start_char`/`end_char` fields are not populated by current chunking strategies. When chunks are not yet available (content ingested but not yet chunked), `context_snippet` serves as fallback. References must be retroactively re-anchored when chunks are created or re-indexed for a content item.

### REQ-REF-002: Reference Extraction from Content

On content ingestion, the system must scan `markdown_content` and `links_json` for:
- arXiv IDs: `arXiv:YYMM.NNNNN`, `arxiv.org/abs/YYMM.NNNNN`, `arxiv.org/pdf/YYMM.NNNNN`
- DOIs: `doi.org/10.xxx`, `DOI: 10.xxx`
- Semantic Scholar URLs: `semanticscholar.org/paper/.../HASH`
- Internal content URLs (matching the application's own URL patterns)
- Generic URLs from `links_json` (lower confidence)

Extracted identifiers must be normalized (strip version suffixes, lowercase DOIs, remove URL prefixes).

Reference storage MUST use `INSERT ... ON CONFLICT DO NOTHING` (not session-level dedup) to handle duplicates atomically. This avoids the `autoflush=False` gotcha where newly added rows within the same batch are invisible to subsequent dedup checks.

### REQ-REF-003: Background Resolution

The system must provide a queue-based background job (`resolve_references`) that:
- Queries unresolved `content_references` rows
- Attempts resolution via GIN-indexed `metadata_json` containment queries
- Attempts resolution via `source_url` matching
- Updates `resolution_status`, `target_content_id`, and `resolved_at` on success
- Processes in configurable batch sizes (default 100)

### REQ-REF-004: Reverse Resolution on Ingestion

When new content is ingested, the system must check for existing unresolved references that match:
- The new content's `arxiv_id` in `metadata_json`
- The new content's `doi` in `metadata_json`
- The new content's `source_url`

Matching references must be automatically resolved (set `target_content_id`, update status).

### REQ-REF-005: Neo4j Citation Edge Projection

Resolved references must be projected to Neo4j as edges:
- Edge type: `CITES` (from source Episode to target Episode)
- Edge properties: `reference_type`, `confidence`, `synced_at`
- Only resolved references with both `source_content_id` and `target_content_id` are synced
- Sync is one-way (PG → Neo4j), fire-and-forget, failure-safe

### REQ-REF-006: Auto-Ingest Trigger (Optional)

When enabled via `reference_auto_ingest_enabled` setting:
- Unresolved references with structured IDs (arXiv, DOI) trigger content ingestion
- arXiv IDs trigger `ingest_arxiv_paper()`
- DOIs trigger `ingest_scholar_paper()`
- Depth tracking via `metadata_json.auto_ingest_depth` integer: 0 for user-ingested, 1 for first-level auto-ingest, etc. Content with `auto_ingest_depth >= max_depth` does not trigger further auto-ingestion
- Auto-ingested content is tagged with both `ingestion_mode: "auto_ingest"` and `auto_ingest_depth: N` in metadata_json

### REQ-REF-007: Supplementary Links (Scholar ↔ arXiv)

When both a Scholar abstract and an arXiv full-text record exist for the same paper:
- Create **two** `supplements` reference rows (one in each direction: Scholar→arXiv and arXiv→Scholar) for true bidirectionality — avoids requiring symmetric query logic
- Detection via shared `arxiv_id` in `metadata_json`
- Created during ingestion of whichever record arrives second

### REQ-REF-008: API Endpoints

- `GET /api/v1/contents/{id}/references` — list references FROM this content (outgoing citations)
- `GET /api/v1/contents/{id}/cited-by` — list references TO this content (incoming citations)
- Response includes: reference_type, resolution_status, target content summary (if resolved), external_url/id (if unresolved)

### REQ-REF-009: CLI Commands

- `aca manage extract-refs` — backfill references for existing content
  - Options: `--after DATE`, `--before DATE`, `--source SOURCE_TYPE`, `--dry-run`, `--batch-size N`
- `aca manage resolve-refs` — manually trigger resolution pass
  - Options: `--batch-size N`, `--auto-ingest`

### REQ-REF-010: Database Migration

- Create `content_references` table with indexes and CHECK constraint (`chk_has_identifier`)
- Use `VARCHAR(20)` columns with application-level `StrEnum` validation for `reference_type`, `external_id_type`, and `resolution_status` — do NOT create PostgreSQL enum types (avoids `ALTER TYPE ... ADD VALUE` migration burden per CLAUDE.md gotcha)
- Create partial unique index `uq_content_reference_url` using `CREATE UNIQUE INDEX ... WHERE external_id IS NULL` (not a table-level UNIQUE constraint, which does not support WHERE clauses)
- ALTER `contents.metadata_json` from `json` to `jsonb` if not already `jsonb`: `ALTER TABLE contents ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb` (required for GIN index and `@>` containment queries; coordinate with arXiv migration so only the first migration performs the ALTER)
- Create GIN index on `contents.metadata_json` if not already present (idempotent with `CREATE INDEX IF NOT EXISTS`)

### REQ-REF-011: Settings

- `reference_extraction_enabled: bool = True` — enable/disable extraction on ingestion
- `reference_auto_ingest_enabled: bool = False` — enable/disable auto-ingest of unresolved refs
- `reference_auto_ingest_max_depth: int = 1` — prevent recursive auto-ingest
- `reference_neo4j_sync_enabled: bool = True` — enable/disable Neo4j projection
- `reference_min_confidence: float = 0.5` — minimum confidence to store a reference

### REQ-REF-012: Ingestion Hook

All ingestion services must call reference extraction after creating/updating a Content record:
- Extract references from the new content
- Store as `content_references` rows
- Enqueue `resolve_references` background job
- Call reverse resolution to update any existing unresolved refs pointing to the new content
- This hook must be fail-safe: reference extraction failure must not block content ingestion

### REQ-REF-013: MCP Tool Surface

All API endpoints and CLI commands must also be registered as MCP tools in `src/mcp_server.py` via `@mcp.tool()`, following the existing delegation pattern:
- `get_content_references(content_id, direction)` — query outgoing/incoming references
- `extract_references(after, before, source, dry_run, batch_size)` — backfill extraction
- `resolve_references(batch_size, auto_ingest)` — trigger resolution pass
- `ingest_reference(reference_id)` — ad-hoc ingest for a specific unresolved reference

This ensures agentic workflows (MCP clients, AI assistants) have the same citation discovery and ingestion capabilities as the API and CLI.

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
