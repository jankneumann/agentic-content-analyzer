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

#### JSONL File Format

The first line of the JSONL file is always a **manifest record**. Subsequent lines are **data records**, one per row, grouped by table in topological order.

**Manifest (line 1)**:
```json
{"_type": "manifest", "alembic_rev": "abc123", "exported_at": "2026-02-07T12:00:00Z", "tables": {"contents": 150, "summaries": 120, "digests": 10}, "version": 1}
```

**Data records (line 2+)**:
```json
{"_type": "row", "table": "contents", "data": {"id": 42, "content_hash": "sha256:...", "source_type": "rss", ...}}
{"_type": "row", "table": "contents", "data": {"id": 43, "content_hash": "sha256:...", "source_type": "gmail", ...}}
{"_type": "row", "table": "summaries", "data": {"id": 1, "content_id": 42, ...}}
```

The `_type` discriminator enables forward-compatible extensions (e.g., `_type: "neo4j_node"` for combined exports). The `version` field in the manifest enables format evolution.

**Validation on import**: The importer reads line 1, validates it as a manifest (required fields: `_type`, `alembic_rev`, `tables`), then processes data records. Malformed lines are skipped with an error logged (line number + raw content).

### Decision: Cypher export for Neo4j
**Rationale**: Neo4j's APOC export to JSON/Cypher is the standard approach. Export nodes and relationships as JSON, import via `apoc.load.json()` or batch Cypher statements. This works across Neo4j versions and between Community/AuraDB.

#### Neo4j JSONL File Format

Neo4j exports use the same JSONL structure as PG exports but with different `_type` values:

**Manifest (line 1)**:
```json
{"_type": "neo4j_manifest", "exported_at": "2026-02-07T12:00:00Z", "nodes": {"Episode": 50, "Entity": 200, "Relation": 300}, "relationships": {"HAS_ENTITY": 150, "RELATES_TO": 300}, "version": 1}
```

**Node records**:
```json
{"_type": "neo4j_node", "label": "Entity", "uuid": "abc-123", "properties": {"name": "GPT-4", "type": "technology", "summary": "...", "created_at": "..."}}
```

**Relationship records**:
```json
{"_type": "neo4j_relationship", "type": "RELATES_TO", "source_uuid": "abc-123", "target_uuid": "def-456", "properties": {"weight": 0.8, "created_at": "..."}}
```

**Excluded properties**: `embedding`, `*_embedding`, `*_vector` — vector embeddings are large, rebuilt by Graphiti, and not portable across Neo4j versions.

### Decision: Independent database sessions for sync operations
**Rationale**: The codebase uses global engine/session singletons (`_provider`, `_engine`, `_session_factory` in `database.py`) for the application's normal operation. Sync operations require either: (a) reading from source DB and writing to target DB simultaneously (for `push`), or (b) reading from a different DB than the application default (for `export`/`import` with `--from-profile`/`--to-profile`).

Rather than refactoring the global session infrastructure, sync modules create **independent SQLAlchemy engines** using the `DATABASE_URL` from `resolve_profile_settings()`:

```python
from sqlalchemy import create_engine
source_engine = create_engine(source_settings.database_url)
target_engine = create_engine(target_settings.database_url)
```

These engines are short-lived (created per sync operation, disposed after completion) and do NOT interact with the global `_engine` singleton. The `pg_exporter` and `pg_importer` accept an engine parameter rather than using the global session factory. This keeps sync completely decoupled from the application's database layer.

### Decision: Schema check runs before any data transaction
**Rationale**: The Alembic revision check (Task 3.7) is a pre-flight gate that runs BEFORE opening any data import transaction. If the check fails, the import aborts immediately with zero data written. The per-table commit strategy (N18) only applies to the data import phase, which begins after the schema check passes. This means:
1. Schema check → read `alembic_version` table (read-only query, no transaction needed)
2. If check fails → abort, no data written
3. If check passes → begin data import with per-table commits

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

**Import processing order per record**: (1) Remap FK columns using `IDMapper` → (2) Validate enum values → (3) Look up natural key in target DB (using remapped FK values for composite keys like `(content_id, created_at)`) → (4) Based on mode: skip/update/insert → (5) Record old→new ID mapping in `SyncState.id_map`.

This ordering is critical: natural key lookup for child tables (summaries, audio_digests, etc.) uses composite keys that include remapped FK values. The FK must be remapped BEFORE the natural key check, or the lookup will use source IDs that don't exist in the target.

**Import modes**:
- `merge`: Check natural key → if exists, skip (log at INFO: `Skipping {table} row: natural key match found`). If not, insert and add to id_map.
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

**Implementation note**: The enum catalog in `constants.py` should be derived from the actual SQLAlchemy/Python enum classes (e.g., `ContentSource`, `DigestType`) via introspection, not hardcoded. This ensures the catalog stays synchronized as the schema evolves. Example: `ENUM_CATALOG = {col: set(enum_cls) for col, enum_cls in ENUM_COLUMNS.items()}`.

### Decision: Profile-based source/target resolution
**Rationale**: Leveraging the existing profile system (`profiles/*.yaml`) for connection details. The `--from-profile` and `--to-profile` flags resolve database URLs, Neo4j URIs, etc. without requiring users to manage connection strings manually.

### Decision: File storage sync via `FileStorageProvider` interface
**Rationale**: The existing `FileStorageProvider` abstract base class provides a unified `get(path)` / `put(path, data)` / `exists(path)` / `list_files(prefix)` interface across all storage providers (local via `LocalFileStorage`, S3 via `S3FileStorage`, Supabase via `SupabaseFileStorage`, Railway MinIO via `RailwayFileStorage`). The factory function `get_storage(bucket)` returns the appropriate provider. File sync reads from source provider and writes to target provider using these methods. Files are discovered by querying the **source** database for file path references (see File Path Reference Map above) rather than blind bucket enumeration — this ensures only referenced files are synced.

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

### Decision: CLI flag semantics — `--force` vs `--yes`
**Rationale**: Two distinct confirmation-bypass flags serve different purposes:
- **`--force`**: Overwrite an existing output file on `aca sync export`. Only applies to export. Does NOT skip destructive database prompts.
- **`--yes`**: Skip the confirmation prompt for `--mode clean` truncation on `aca sync import`. Only applies to import. Does NOT force-overwrite files.

These flags are scoped to their respective commands and are never combined. `aca sync push` inherits `--yes` (for clean mode on import) but not `--force` (push always writes to a temp export file internally, no overwrite scenario).

### Decision: Profile resolution — active profile as default, explicit error without profile
**Rationale**: When `--from-profile` or `--to-profile` is omitted, the active profile (from `PROFILE` env var) is used as the default. If no profile is active and no `--from-profile`/`--to-profile` is provided, the command uses the current `Settings()` resolution (env vars + `.env` file) without profile YAML. For `aca sync push` specifically, both `--from-profile` and `--to-profile` are required (no default — sync direction must be explicit).

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

## Implementation Notes (Medium/Low Severity Findings)

These findings were identified during plan review but deferred from critical/high fixes. They should be addressed during implementation of the relevant tasks.

### PG Import (Tasks 3.x)

| # | Severity | Finding | Implementation Guidance |
|---|----------|---------|------------------------|
| N1 | MEDIUM | **JSONL format validation**: No validation of JSONL integrity before import. Malformed JSON lines, missing table name fields, or type mismatches could crash the importer. | Task 3.1: Add a validation pass before import. Read JSONL manifest first, verify structure. On malformed line, log line number + error, skip that record, continue. Report total parse errors in summary. |
| N2 | MEDIUM | **`--tables` + `--mode clean` scope**: If user specifies `--tables contents --mode clean`, should only `contents` be truncated, or also its dependents (summaries, images, etc.)? Truncating only `contents` leaves orphaned FK references. | Task 3.6: Truncate only specified tables (plus auto-included parents). Log warning: `--mode clean with --tables may leave orphaned child records in: summaries, images, digests`. Consider adding `--cascade` flag in future. |
| N3 | MEDIUM | **Multiple Alembic heads**: If target DB has multiple Alembic heads (branched migrations), `alembic_version` may contain multiple rows. Schema check should detect this. | Task 3.7: After querying `alembic_version`, if multiple rows found, error: `Target DB has multiple Alembic heads — run 'alembic merge heads' to linearize migrations before importing.` |
| N4 | MEDIUM | **Dry-run + clean mode interaction**: When `--dry-run --mode clean` is used, should the confirmation prompt still appear? Dry-run shouldn't write anything, but the prompt gives false sense of action. | Task 7.7: In dry-run mode, skip the clean confirmation prompt. Instead log: `[DRY RUN] Would truncate tables: {list}. No data modified.` |
| N5 | MEDIUM | **Empty target database**: No scenario covers importing into a completely fresh database (no existing rows). The dedup lookup should handle empty tables gracefully (no-op, not error). | Task 3.2: Natural key lookup on empty table returns no match → all records inserted. This should be the default behavior. Add a test case for round-trip into empty DB. |
| N6 | LOW | **Deprecated enum values**: If source export contains an enum value that was valid in the source schema but deprecated/removed in the target schema, import should handle gracefully. | Task 3.5: Enum validation already skips unknown values. For deprecated values specifically, they'll still be in the target schema enum (PG ALTER TYPE ADD VALUE is permanent). No additional handling needed unless a value was truly removed, which requires a new migration. |

### Neo4j Sync (Tasks 4.x, 5.x)

| # | Severity | Finding | Implementation Guidance |
|---|----------|---------|------------------------|
| N7 | MEDIUM | **Neo4j property filtering**: Graphiti stores vector embeddings and internal index metadata on nodes. These should NOT be exported (large, rebuild-able). | Task 4.2: Explicitly exclude properties matching patterns: `embedding`, `*_embedding`, `*_vector`. Export all other properties including `name`, `type`, `created_at`, `summary`, `metadata`. Document excluded property patterns in constants.py. |
| N8 | MEDIUM | **Neo4j export/import sequencing**: Neo4j import must not run concurrently with Graphiti operations. Export uses read-only queries (safe). Import modifies graph state. | Task 5.1: Document that Neo4j import is a blocking operation. If Graphiti is running (e.g., entity extraction), import should warn or fail. In practice, sync is a CLI operation run manually — concurrent Graphiti usage is unlikely. |

### File Storage Sync (Tasks 6.x)

| # | Severity | Finding | Implementation Guidance |
|---|----------|---------|------------------------|
| N9 | MEDIUM | **`--files-only` requires PG connection**: File discovery queries the source database for file path references. Using `--files-only` still needs a source DB connection, which may surprise users who expect `--files-only` to bypass PG entirely. | Task 7.5: Document in CLI help: `--files-only: Sync only file storage (requires database connection for file path discovery)`. Error if DB connection fails with: `File discovery requires database access. Check source profile database configuration.` |
| N10 | MEDIUM | **File skip strategy for changed files**: Current design skips files that exist on target (by path). But if a source file has been updated (newer/different content), the target copy becomes stale. | Task 6.4: Default: skip if path exists (simple, fast). Future enhancement: add `--force-files` flag to re-upload all files regardless of existence. Content-hash comparison is too expensive for large audio files (50-100MB). |
| N11 | MEDIUM | **Profile-based storage provider instantiation**: `resolve_profile_settings()` must return enough context to construct a `FileStorageProvider` for each profile without activating as global PROFILE. Need to verify the `get_storage()` factory supports this. | Task 0.2: Audit `src/services/file_storage.py` factory. Add a `get_storage_for_settings(settings, bucket)` function that accepts a Settings instance (not reading from global settings). |
| N12 | LOW | **Same-storage provider edge case**: If source and target profiles use the same storage provider pointing to the same bucket/path, file sync would copy files onto themselves (no-op but wasteful). | Task 6.1: After resolving source and target storage configs, compare provider type + bucket config. If identical, log: `Source and target storage are the same — skipping file sync.` Skip the file sync phase entirely. |

### CLI / Integration (Tasks 7.x, 8.x)

| # | Severity | Finding | Implementation Guidance |
|---|----------|---------|------------------------|
| N13 | MEDIUM | **Profile loading API audit**: Task 8.1 assumes `Settings.from_profile(name)` or equivalent exists. The current profile system loads via `PROFILE` env var in Settings.__init__. Need to verify or create a method that loads a profile without side effects. | Task 8.1: Read `src/config/settings.py` carefully. If no `from_profile()` exists, implement `resolve_profile_settings(name)` that: reads `profiles/{name}.yaml`, resolves `${VAR}` from `.secrets.yaml`, returns a `Settings` instance. Do NOT set env vars. |
| N14 | LOW | **Dry-run for file sync preview**: The `--dry-run` flag is specified for PG import but not explicitly for file sync. Should file sync also support dry-run? | Task 7.7: Yes — `--dry-run` should apply to all sync phases. For file sync, report: `Would copy {N} files ({size} total) from {source_provider} to {target_provider}. Files: {list}`. No actual file I/O. |
| N15 | LOW | **Incremental sync business rationale**: Proposal doesn't explain why incremental sync matters. | Context: Incremental sync enables repeated dev→cloud syncing during active development without retransferring unchanged data (e.g., sync local → Railway after adding 10 new articles, without re-syncing the existing 500). |
| N16 | LOW | **Custom PostgreSQL types**: If the database uses custom types beyond standard enums (e.g., composite types, domains), sync may fail. | Out of scope for v1. All current types are standard SQL + enums. If custom types are added later, they'll need explicit handling in the serializer. Document this as a known limitation. |

### Iteration 2 Findings

| # | Severity | Finding | Implementation Guidance |
|---|----------|---------|------------------------|
| N17 | MEDIUM | **Multi-profile Settings isolation**: `Settings` loads from `PROFILE` env var globally. `resolve_profile_settings()` must construct a `Settings` instance from a named profile's YAML without mutating env or global state. Same for storage providers — needs a `get_storage_for_settings(settings, bucket)` function. | Task 0.1: Implement as a standalone function, NOT a Settings classmethod that touches `os.environ`. Read the profile YAML, merge with base, resolve `${VAR}` from `.secrets.yaml`, construct `Settings` kwargs dict, return `Settings(_env_file=None, **kwargs)`. |
| N18 | MEDIUM | **Transaction scope for import**: Large imports touching 10k+ rows in a single transaction can hold locks for too long and OOM on Railway Hobby tier. | Task 3.1: Use a single transaction for correctness (FK consistency), but commit per-table rather than per-file. If per-table commit, process tables in dependency order so partial failures leave a consistent state (orphaned children are acceptable, orphaned parents are not). |
| N19 | MEDIUM | **Export file size estimation**: No way to estimate file size before export begins. For large DBs, users may run out of disk space mid-export. | Task 2.5: Before export, query `SELECT COUNT(*) FROM {table}` for each table and log estimated row counts. After export, report actual file size. No pre-flight disk space check (too platform-dependent). |
| N20 | MEDIUM | **`aca sync push` orchestration error recovery**: If PG import fails mid-way but file sync already completed, the state is partially synced. No rollback for file sync. | Task 7.4: File sync is idempotent (skip-existing), so partial state is safe — re-running push will skip already-copied files. Document: `push` is designed for re-runnability, not atomicity. Log which stages completed on failure. |
| N21 | MEDIUM | **Neo4j JSONL format**: Neo4j export shares the same JSONL file format as PG export but uses different `_type` values. Define them. | Task 4.1: Use `_type: "neo4j_node"` for nodes and `_type: "neo4j_relationship"` for relationships. Include `label` (node type), `uuid`, `properties`. Manifest uses `_type: "neo4j_manifest"` with node/relationship counts per label. |
| N22 | LOW | **Alembic revision comparison**: Design says "target older" and "target newer" but Alembic revisions are hash strings, not orderable. Need to walk the revision chain to determine relative ordering. | Task 3.7: Use `MigrationContext` to get current target revision. Compare against source revision from manifest. If they match → proceed. If target revision is NOT an ancestor of source → block (target is behind or diverged). Use `alembic.script.ScriptDirectory.walk_revisions()` to check ancestry. If ancestry can't be determined (diverged branches), warn and proceed. |
| N23 | MEDIUM | **Dual DB session management**: Sync modules need independent SQLAlchemy engines (not the global `_engine` singleton). Export/import classes must accept an engine parameter. | Task 2.1, 3.1: Constructor signature: `PGExporter(engine: Engine)` and `PGImporter(engine: Engine)`. Create engines from `resolve_profile_settings().database_url`. Dispose engines after sync completes. |
| N24 | MEDIUM | **Self-referential FK update timing**: The batch UPDATE for `contents.canonical_id` and `digests.parent_digest_id` must run AFTER all rows in the table are inserted but BEFORE moving to Level 1 tables. The `id_map` must be fully populated for Level 0 before self-ref updates. | Task 3.4: Sequence within Level 0: (1) insert all contents rows with `canonical_id=NULL` → (2) populate id_map → (3) batch UPDATE `canonical_id` using id_map → (4) proceed to Level 1. Same for digests. |
| N25 | LOW | **File discovery pagination**: Querying all file paths at once may use excessive memory on large DBs. | Task 6.2: Use server-side cursor or `yield_per(1000)` for file path queries. Process in batches rather than loading all paths into a list. |
| N26 | LOW | **`Digest.parent_digest_id` FK not in SQLAlchemy model**: The column is defined as `Column(Integer, nullable=True)` with comment `# FK added in migration`. The FK constraint exists at the DB level (migration-managed), but not in the model metadata. Sync uses explicit `constants.py` DAG for FK discovery (not model introspection), so this is not blocking. | Task 1.3: Define `digests.parent_digest_id → digests.id` explicitly in `TABLE_DEPENDENCIES` and `SELF_REF_FKS` constants. Do NOT rely on SQLAlchemy model metadata for FK discovery. |

## Resolved Questions

1. **File storage sync — included.** Images, podcasts, and audio-digests are synced between storage providers using the `FileStorageProvider` interface. Files are discovered via database references (not blind enumeration).
2. **Partial table sync — supported.** `--tables contents,summaries` syncs only specified tables plus FK parents. Low complexity due to shallow dependency graph (max depth 2).
3. **Neo4j indexes — rebuilt separately.** Sync exports only data entries (Episode, Entity, Relation nodes + relationships). Graphiti indexes/constraints are rebuilt via `build_indices_and_constraints()` after import.
