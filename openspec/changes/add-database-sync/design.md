## Context

The newsletter aggregator uses a multi-provider database architecture:
- **PostgreSQL**: 4 providers (local, Supabase, Neon, Railway) storing relational data (~12 tables including contents, summaries, digests, themes, images, audio_digests, podcasts, jobs)
- **Neo4j**: 2 providers (local Docker, AuraDB) storing knowledge graph data (entities, relationships, episodes via Graphiti)

Each provider has different connection parameters, pool settings, and capabilities. Currently, switching providers means starting with an empty database and re-ingesting everything.

### Stakeholders
- Developers switching between local and cloud environments
- CI/CD pipelines needing test data seeding
- Backup/restore workflows (complementing Railway's pg_cron backups)

## Goals / Non-Goals

### Goals
- Enable bidirectional sync between any two PostgreSQL providers
- Enable bidirectional sync between local Neo4j and AuraDB
- Support both full and incremental sync modes
- Profile-aware: resolve source/target from profile configuration
- Portable intermediate format (not provider-specific)
- Handle FK relationships and content deduplication gracefully

### Non-Goals
- Real-time replication (CDC/logical replication) — too complex, not needed
- Schema migration management — Alembic handles this separately
- Cross-database foreign key mapping for Neo4j ↔ PostgreSQL links — knowledge graph is independently queryable
- Preserving Neo4j Graphiti indexes/constraints during sync — rebuild separately via `graphiti.build_indices_and_constraints()`

## Decisions

### Decision: JSONL as intermediate format for PostgreSQL
**Rationale**: JSONL (newline-delimited JSON) is human-readable, streamable, and doesn't require additional dependencies. Each line is a self-contained record with table name and data. This is preferable to:
- **pg_dump/pg_restore**: Provider-specific, doesn't work across different PostgreSQL deployments cleanly (extension differences, permission issues)
- **SQLite**: Binary format, harder to inspect/debug, adds dependency
- **CSV**: Doesn't handle nested JSON fields (tables_json, metadata_json, links_json) cleanly

### Decision: Cypher export for Neo4j
**Rationale**: Neo4j's APOC export to JSON/Cypher is the standard approach. Export nodes and relationships as JSON, import via `apoc.load.json()` or batch Cypher statements. This works across Neo4j versions and between Community/AuraDB.

### Decision: Two-phase sync (export → import) with intermediate files
**Rationale**: Rather than a direct database-to-database connection (which would require both databases accessible simultaneously), the export/import approach:
1. Decouples source and target — can sync to a file, transfer it, import later
2. Enables inspection of what's being synced before applying
3. Works even when source and target are on different networks
4. Enables backup-as-sync — exported files double as backups

### Decision: Natural key deduplication with SyncState tracking (not ID-based)
**Rationale**: Auto-increment IDs differ across databases. Each table uses a natural key for dedup (see Natural Keys table above). The `content_hash` (SHA-256) on the Content model is the primary dedup key for contents; other tables use composite keys. During import, the importer builds a `SyncState` that tracks:

```python
class SyncState:
    id_map: dict[str, dict[int, int]]   # {table_name: {old_id: new_id}}
    uuid_map: dict[str, dict[str, str]] # {table_name: {old_uuid: new_uuid}}
    hash_map: dict[str, int]            # {content_hash: new_content_id}
    stats: dict[str, ImportStats]       # {table_name: {inserted, skipped, updated, failed}}
    errors: list[SyncError]             # Accumulated non-fatal errors
```

The `id_map` is populated as parent tables are inserted (Level 0 first, then Level 1, etc.). Child table FK columns are remapped by looking up the old FK value in `id_map[parent_table]`. If a lookup fails, the record is skipped with an error logged (not a hard failure — allows partial imports).

**Import modes**:
- `merge`: Check natural key → if exists, skip. If not, insert and add to id_map.
- `replace`: Check natural key → if exists, update in place (preserving target ID). If not, insert.
- `clean`: Truncate all target tables (reverse dependency order), then insert all records (no dedup needed).

### Decision: Topological table ordering for FK safety
**Rationale**: Tables have FK dependencies (e.g., summaries → contents, digests → contents). Export and import must follow dependency order:
1. Export order: parents first (contents → summaries → digests → ...)
2. Import order: same (parents before children)
3. On import, remap FK references using old→new ID mapping built during insert

#### Table Dependency DAG (from SQLAlchemy models)

```
Level 0 (no FK parents):
  contents           (self-ref: canonical_id → contents.id)
  digests             (self-ref: parent_digest_id → digests.id)
  theme_analyses
  conversations
  prompt_overrides

Level 1 (depends on Level 0):
  summaries           → contents.id (content_id)
  chat_messages       → conversations.id (conversation_id)

Level 2 (depends on Level 0-1):
  images              → contents.id (source_content_id)
                      → summaries.id (source_summary_id)
                      → digests.id (source_digest_id)
  audio_digests       → digests.id (digest_id)
  podcast_scripts     → digests.id (digest_id)

Level 3 (depends on Level 2):
  podcasts            → podcast_scripts.id (script_id)
```

**Export order**: Level 0 → Level 1 → Level 2 → Level 3.
**Import order**: Same. Within each level, order is arbitrary.
**Clean mode truncation**: Reverse order (Level 3 → Level 2 → Level 1 → Level 0).

**Tables excluded from sync** (managed by external systems):
- `pgqueuer_jobs` — transient job queue, recreated by PGQueuer
- `alembic_version` — schema metadata, managed by Alembic

**Self-referential FK handling**: `contents.canonical_id` and `digests.parent_digest_id` reference rows in the same table. Import uses a two-pass approach: (1) insert all rows with self-ref FKs set to NULL, (2) update self-ref FKs using the ID mapping after all rows are inserted.

#### Natural Keys per Table (for deduplication)

| Table | Natural Key | Dedup Strategy |
|-------|------------|----------------|
| contents | `content_hash` (SHA-256) | Primary dedup key; also `(source_type, source_id)` as unique constraint |
| summaries | `(content_id, created_at)` | Match by remapped content_id + timestamp |
| digests | `(digest_type, period_start, period_end)` | Match by type and date range |
| images | `id` (UUID) | UUID is globally unique; MERGE on UUID |
| audio_digests | `(digest_id, created_at)` | Match by remapped digest_id + timestamp |
| podcast_scripts | `(digest_id, created_at)` | Match by remapped digest_id + timestamp |
| podcasts | `(script_id, created_at)` | Match by remapped script_id + timestamp |
| theme_analyses | `(analysis_date, start_date, end_date)` | Match by date range |
| conversations | `id` (UUID string) | UUID is globally unique; MERGE on UUID |
| chat_messages | `id` (UUID string) | UUID is globally unique; MERGE on UUID |
| prompt_overrides | `key` (unique) | Match by key name |

#### File Path Reference Map (for file storage sync)

| Table | Column | Bucket |
|-------|--------|--------|
| images | `storage_path` | `images` |
| audio_digests | `audio_url` | `audio-digests` |
| podcasts | `audio_url` | `podcasts` |

File discovery queries the SOURCE database for non-NULL values in these columns.

#### Enum Catalog (for import validation)

| Column | Enum Type | Values |
|--------|----------|--------|
| contents.source_type | ContentSource | gmail, rss, file_upload, youtube, podcast, substack, manual, webpage, other |
| contents.status | ContentStatus | pending, parsing, parsed, processing, completed, failed |
| digests.digest_type | DigestType | daily, weekly, sub_digest |
| digests.status | DigestStatus | PENDING, GENERATING, COMPLETED, FAILED, PENDING_REVIEW, APPROVED, REJECTED, DELIVERED |
| images.source_type | ImageSource | extracted, keyframe, ai_generated |
| audio_digests.status | AudioDigestStatus | pending, processing, completed, failed |

During import, enum values from the export are validated against the target schema. Unknown enum values cause the record to be skipped with a warning (not a hard error) — the source may have newer enum values from a later schema version.

### Decision: Profile-based source/target resolution
**Rationale**: Leveraging the existing profile system (`profiles/*.yaml`) for connection details. The `--from-profile` and `--to-profile` flags resolve database URLs, Neo4j URIs, etc. without requiring users to manage connection strings manually.

### Decision: File storage sync via `FileStorageService` interface
**Rationale**: The existing `FileStorageService` provides a unified `get(path)` / `put(path, data)` / `exists(path)` / `list_files(prefix)` interface across all storage providers (local, S3, Supabase, Railway MinIO). File sync reads from source provider and writes to target provider using these methods. Files are discovered by querying the **source** database for file path references (see File Path Reference Map above) rather than blind bucket enumeration — this ensures only referenced files are synced.

The three buckets to sync: `images`, `podcasts`, `audio-digests`.

**Sync ordering for `aca sync push`**: (1) PG export from source → (2) discover file paths from source DB → (3) copy files from source storage to target storage → (4) PG import into target → (5) Neo4j export from source → (6) Neo4j import into target. Files are discovered from the source DB (not target) because the target may not have the records yet. PG import happens after file sync so that file path references in the imported records already point to files that exist in target storage.

**Missing source files**: If a database-referenced file is missing from source storage, the syncer logs a warning and skips that file (non-fatal).

### Decision: Partial table sync with automatic FK dependency inclusion
**Rationale**: The most common sync use case is contents + summaries (the core data that takes time to ingest and process). Supporting `--tables` with auto-inclusion of FK parents keeps complexity low. The dependency resolver computes **transitive closure** — requesting a leaf table auto-includes all ancestors:

```
Static dependency map (table → direct parents):
  contents         → []
  summaries        → [contents]
  digests          → []
  images           → [contents, summaries, digests]
  audio_digests    → [digests]
  podcast_scripts  → [digests]
  podcasts         → [podcast_scripts, digests]  (transitive)
  theme_analyses   → []
  conversations    → []
  chat_messages    → [conversations]
  prompt_overrides → []
```

Examples:
- `--tables summaries` → auto-includes `contents` (1 level up)
- `--tables podcasts` → auto-includes `podcast_scripts` AND `digests` (2 levels up)
- `--tables images` → auto-includes `contents`, `summaries`, `digests` (all 3 FK parents)

Max depth is 3 (podcasts → podcast_scripts → digests). Each auto-included table logs: `[INFO] Auto-including parent table: {table} (required by {child}.{fk_column})`.

### Decision: Schema compatibility gate — block import if target is behind, with migration instructions
**Rationale**: Importing data into a database with an older Alembic revision will fail (missing columns, enum values, etc.). Rather than auto-running migrations (which mixes concerns and can be surprising), the import command checks revisions and blocks if the target is behind:
- **Target same as source**: Proceed normally.
- **Target older than source**: Block with clear error: `"Target database is at revision {target_rev}, but export requires {source_rev}. Run: PROFILE={target_profile} alembic upgrade head"`.
- **Target newer than source**: Proceed with warning (safe — new columns are nullable and have defaults).

This keeps `aca sync import` a pure data operation and `alembic upgrade head` a separate explicit schema operation.

### Decision: Neo4j sync exports entries only, indexes rebuilt separately
**Rationale**: Graphiti manages its own indexes and constraints (vector indexes, full-text indexes, uniqueness constraints). These are schema-level concerns, not data. Exporting and reimporting them would be fragile across Neo4j versions and Community vs AuraDB. Instead, after import, run `graphiti.build_indices_and_constraints()` to rebuild them. This keeps the sync focused purely on data (Episode, Entity, Relation nodes + relationships).

## Risks / Trade-offs

- **Large datasets**: For very large databases (100k+ records), JSONL export could be slow. Mitigation: streaming writes, progress bars, optional table filtering.
- **Schema version mismatch**: If source and target are on different Alembic revisions, import may fail. Mitigation: include Alembic revision in export metadata, warn if mismatch.
- **Neo4j Graphiti internals**: Graphiti manages its own Neo4j schema (node labels, relationship types, indexes). Mitigation: export/import entries at the Cypher level (not Graphiti API level), rebuild indexes separately via `build_indices_and_constraints()`.
- **File storage size**: Large podcast audio files (50-100MB each) could make sync slow over the network. Mitigation: skip file sync with `--pg-only`, support `--buckets images` to sync only specific buckets, progress reporting per file.
- **Concurrent modifications**: If data is being ingested while sync runs, there could be inconsistencies. Mitigation: optional `--lock` flag to pause ingestion during sync (non-default).

## Migration Plan

1. One optional Alembic migration: `sync_metadata` table for incremental sync tracking (columns: `id`, `source_profile`, `target_profile`, `last_sync_timestamp`, `tables_synced`, `record_count`, `status`). Unique constraint on `(source_profile, target_profile)`.
2. Install new `src/sync/` module and CLI commands
3. Alembic revision stored in export metadata for compatibility checking
4. Rollback: drop `sync_metadata` table and remove the sync module — no other database state is modified by the feature itself (only the target database is modified during import)

## Resolved Questions

1. **File storage sync — included.** Images, podcasts, and audio-digests are synced between storage providers using the `FileStorageService` interface. Files are discovered via database references (not blind enumeration).
2. **Partial table sync — supported.** `--tables contents,summaries` syncs only specified tables plus FK parents. Low complexity due to shallow dependency graph (max depth 2).
3. **Neo4j indexes — rebuilt separately.** Sync exports only data entries (Episode, Entity, Relation nodes + relationships). Graphiti indexes/constraints are rebuilt via `build_indices_and_constraints()` after import.
