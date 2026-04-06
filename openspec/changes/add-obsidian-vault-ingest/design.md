# Technical Design: Obsidian Vault Ingestion Bridge

## 1. Overview

This design adds an ingestion adapter that reads Obsidian Web Clipper notes from a synced vault folder and converts them into ACA's existing content ingestion pipeline input.

### Design Goals

1. Reuse existing ACA ingestion flow and storage model
2. Make capture cross-platform via Obsidian Web Clipper + sync providers
3. Ensure idempotent, retry-safe processing under eventual consistency
4. Minimize user setup complexity while preserving security boundaries

### Non-Goals (v1)

- Writing processed output back into Obsidian notes
- Hard dependency on one sync provider
- Full parser support for every custom clipper template variation

## 2. Architecture

```text
Obsidian Web Clipper
        |
        v
Vault folder (synced locally)
  e.g. ~/Vault/Inbox/WebClipper
        |
        v
Vault Queue Reader (poller, optional watcher trigger)
        |
        v
File Stabilizer (settle window + lock/temp filters)
        |
        v
Obsidian Note Parser (frontmatter + markdown normalization)
        |
        v
Canonicalizer + Deduper (URL primary, file hash secondary)
        |
        v
Existing ACA ingestion job enqueue
        |
        v
Existing extraction/analysis/indexing pipeline
```

## 3. Components

### 3.1 Config Surface

Add config keys:

- `OBSIDIAN_VAULT_PATH` (absolute path)
- `OBSIDIAN_INGEST_FOLDER` (relative vault path; default `Inbox/WebClipper`)
- `OBSIDIAN_POLL_INTERVAL_SECONDS` (default 30)
- `OBSIDIAN_FILE_SETTLE_MS` (default 3000)
- `OBSIDIAN_MOVE_PROCESSED_TO` (optional relative path)

Validation rules:

- Vault path must exist and be directory
- Ingest folder must resolve under vault root
- Reject path traversal (`..`) and symlink escapes by resolving real paths

### 3.2 Vault Queue Reader

Primary mode: periodic poller over `*.md` files in ingest folder.

Optional optimization: file watcher can trigger early scans but never replaces poller. Poller remains source of truth for reliability across sync backends.

Reader responsibilities:

- Enumerate candidate files
- Read stat metadata (`size`, `mtime`)
- Consult ingest state table
- Defer unstable files to later scan

### 3.3 File Stabilizer

A file is considered stable when:

- It has no known temporary/lock filename pattern
- Its `(size, mtime)` pair is unchanged across one settle interval

Temp/lock skip patterns (initial):

- `*.tmp`, `*.swp`, `*.part`, `*.crdownload`
- names prefixed by `.~` or suffixed `.icloud`

### 3.4 Parser + Normalizer

Input: UTF-8 markdown note with YAML frontmatter.

Required fields (v1):

- `source_url`
- `captured_at`

Optional fields:

- `capture_client` (default `obsidian-web-clipper`)
- `content_type_hint`

Normalization behavior:

- Convert wikilinks `[[Page]]` to plain text fallback
- Flatten embeds where safe; otherwise retain link text
- Strip or normalize callout syntax into blockquotes
- Preserve body markdown for downstream parser compatibility

### 3.5 Canonicalization and Dedup

Dedup key hierarchy:

1. Canonical URL hash (primary)
2. File content hash (secondary fallback)

Canonical URL rules (initial):

- Lowercase host
- Remove default ports
- Strip common tracking params (`utm_*`, `fbclid`, `gclid`)
- Normalize trailing slash behavior for path

When duplicate URL is detected:

- Reuse existing content record
- Record note-level ingest event (for traceability)

### 3.6 Ingest State Store

Add `obsidian_ingest_state` table (or equivalent persistent store):

- `note_path` (unique)
- `last_seen_mtime`
- `last_seen_size`
- `file_hash`
- `canonical_url_hash`
- `status` (`queued|ingested|failed|deferred`)
- `content_id` (nullable)
- `error_code`, `error_message` (nullable)
- `updated_at`

Purpose:

- Idempotency
- Replay support
- Operational observability

### 3.7 Post-Process Actions

If `OBSIDIAN_MOVE_PROCESSED_TO` is configured:

- Move successfully ingested note to destination folder preserving filename
- On name collision, append deterministic suffix (`-<short-hash>`)

If not configured:

- Keep note in place and rely on state table to avoid re-ingest

## 4. Data Flow

1. Poller scans folder and finds `clip-123.md`
2. Stabilizer waits until file is stable across settle window
3. Parser extracts frontmatter + body
4. Canonicalizer computes URL + hashes
5. Deduper checks existing content by canonical URL
6. Enqueue to existing ingestion (new content or link-to-existing)
7. Update state row to `ingested` or `failed`
8. Optional move to processed folder

## 5. Failure and Replay

Failure classes:

- `parse_error` (invalid YAML/markdown)
- `missing_required_metadata` (`source_url`, `captured_at`)
- `invalid_url`
- `file_unstable`
- `pipeline_enqueue_failure`

Replay triggers:

- Automatic on file change (mtime/size/hash changed)
- Manual retry command targeting `note_path` or failed status set

## 6. Security and Privacy

- Restrict reads to configured vault root subtree
- Avoid executing embedded scripts/macros from note content
- Log minimal content in errors (no full body dumps by default)
- Document sync-provider trust model (metadata may transit third-party cloud)

## 7. Observability

Metrics:

- `obsidian_scan_files_total`
- `obsidian_ingest_attempt_total`
- `obsidian_ingest_success_total`
- `obsidian_ingest_failure_total{error_code}`
- `obsidian_ingest_deferred_total`
- `obsidian_ingest_latency_ms`

Structured logs include:

- `note_path`
- `canonical_url`
- `content_id`
- `status`
- `error_code`

## 8. Rollout Plan

### Phase 1 (MVP)

- Poller only
- Required frontmatter parsing
- URL dedupe
- Basic failure recording

### Phase 2

- Optional watcher trigger
- Processed-folder moves
- Expanded markdown normalization coverage

### Phase 3

- Enhanced template compatibility presets
- Attachment ingestion strategy
- Operational dashboards + alerts

## 9. Open Questions

1. Should `captured_at` fallback to file mtime when absent, or stay strictly required?
2. Should note annotations become first-class linked entities in the data model?
3. What is the desired retention policy for failed note-state records?
4. Which sync providers should be officially supported in docs for v1?
