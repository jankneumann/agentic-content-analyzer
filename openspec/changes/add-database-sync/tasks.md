## Parallelization Guide

```
Phase 1: [1.1, 1.2, 1.3, 1.4] — Core Infrastructure (sequential, critical path)
Phase 2: [2.*] | [4.*] | [6.1, 6.2] — Export + File Discovery (parallel groups)
Phase 3: [3.*] | [5.*] | [6.3-6.6] — Import + File Sync (parallel groups, after Phase 2)
Phase 4: [7.*] + [8.*] — CLI + Profile Integration (sequential, after Phase 3)
Phase 5: [9.*] — Incremental Sync (after Phase 4)
Phase 6: [10.*] | [11.*] — Testing + Docs (parallel, after Phase 5)
```

## 1. Core Sync Infrastructure

- [ ] 1.1 Create `src/sync/__init__.py` with module-level exports
- [ ] 1.2 Create `src/sync/models.py` — Pydantic models: `SyncManifest` (alembic_rev, timestamp, table_counts), `TableExport` (table_name, rows), `SyncRecord` (table, data dict), `SyncState` (id_map, uuid_map, hash_map, stats, errors), `ImportStats` (inserted, skipped, updated, failed), `SyncError` (table, row_index, message)
- [ ] 1.3 Create `src/sync/constants.py` — explicit table dependency DAG (see design.md), supported tables list, natural key definitions per table, enum catalog, file path column map. **This is the single source of truth for all downstream tasks.**
- [ ] 1.4 Create `src/sync/id_mapper.py` — `IDMapper` class that wraps `SyncState.id_map` with methods: `record_mapping(table, old_id, new_id)`, `remap_fk(table, old_id) → new_id | None`, `record_uuid(table, old_uuid, new_uuid)`, `remap_uuid(table, old_uuid) → new_uuid | None`. Handles self-referential FK deferred updates.

## 2. PostgreSQL Export (depends on: 1.3)

- [ ] 2.1 Create `src/sync/pg_exporter.py` — SQLAlchemy-based exporter that reads rows from each table via streaming (yield per batch, not load-all-in-memory) and writes JSONL
- [ ] 2.2 Implement topological table ordering using `TABLE_DEPENDENCIES` from constants.py (Level 0 → 1 → 2 → 3)
- [ ] 2.3 Include Alembic revision and export timestamp in manifest (query `alembic_version` table via `MigrationContext`)
- [ ] 2.4 Support `--tables` filter with transitive FK parent auto-inclusion (log auto-included tables)
- [ ] 2.5 Add progress reporting (table name + row count per table, final summary with total rows and file size)

## 3. PostgreSQL Import (depends on: 1.2, 1.3, 1.4)

- [ ] 3.1 Create `src/sync/pg_importer.py` — reads JSONL, validates manifest, inserts into target database within a transaction
- [ ] 3.2 Implement natural-key deduplication per table using keys from constants.py: check if record exists → skip (merge) or update (replace). Populate `SyncState.id_map` as records are inserted.
- [ ] 3.3 Implement FK remapping — for each child row, look up FK columns in `IDMapper.remap_fk()`. Skip row with warning if parent not found. (depends on: 3.2 populating id_map)
- [ ] 3.4 Implement self-referential FK handling — two-pass for `contents.canonical_id` and `digests.parent_digest_id`: (1) insert with self-ref FK NULL, (2) batch UPDATE using id_map after all rows in table are inserted
- [ ] 3.5 Handle enum validation — validate enum values against catalog from constants.py. Skip row with warning on unknown enum values.
- [ ] 3.6 Support `--mode` flag: `merge` (skip existing), `replace` (upsert matching), `clean` (truncate in reverse dependency order + insert). Clean mode prompts for confirmation (skipped with `--yes`).
- [ ] 3.7 Check Alembic revision compatibility: query target `alembic_version` table. Block if target is behind source (with `PROFILE={target_profile} alembic upgrade head` instructions). Warn if target is ahead. Proceed if same. If `alembic_version` table missing, error with instructions.
- [ ] 3.8 Add progress reporting (per-table: inserted/skipped/updated/failed counts) and error summary (list of SyncError entries)

## 4. Neo4j Export (depends on: 1.1; parallel with Phase 2)

- [ ] 4.1 Create `src/sync/neo4j_exporter.py` — export nodes and relationships via read-only Cypher queries to JSONL
- [ ] 4.2 Export Graphiti node types: Episode, Entity, Relation (edge) with all data properties. Exclude vector embeddings and internal index metadata.
- [ ] 4.3 Include graph metadata (node/relationship counts per label)

## 5. Neo4j Import (depends on: 4.1; sequential after Neo4j export)

- [ ] 5.1 Create `src/sync/neo4j_importer.py` — import nodes and relationships from JSONL via Cypher
- [ ] 5.2 Handle node merging (MERGE on UUID for idempotency). Verify idempotency: re-importing same data produces zero new nodes.
- [ ] 5.3 Support `--mode` flag: `merge` (skip existing nodes by UUID), `clean` (delete all nodes/relationships + import)
- [ ] 5.4 Log reminder to run `graphiti.build_indices_and_constraints()` after import to rebuild indexes

## 6. File Storage Sync (depends on: 1.3 for file path map)

- [ ] 6.1 Create `src/sync/file_syncer.py` — copy files between storage providers using `FileStorageService`
- [ ] 6.2 Discover files from **source** database by querying: `images.storage_path`, `audio_digests.audio_url`, `podcasts.audio_url` (non-NULL only). Map each path to its bucket.
- [ ] 6.3 Support `--buckets images,podcasts,audio-digests` filter for selective bucket sync
- [ ] 6.4 Skip already-existing files on target (by path existence check via `FileStorageService.exists()`)
- [ ] 6.5 Add progress reporting (file name, size, bucket counts, skipped/missing counts)
- [ ] 6.6 Handle source/target storage provider resolution from `--from-profile` / `--to-profile`. Instantiate separate `FileStorageService` for each profile without activating as global PROFILE.

## 7. CLI Commands (depends on: 2.*, 3.*, 4.*, 5.*, 6.*)

- [ ] 7.1 Create `src/cli/sync_commands.py` with Typer app
- [ ] 7.2 Implement `aca sync export` — export from current profile's database to file. Paths relative to CWD or absolute. Error if output file exists (unless `--force`). Create parent dirs if needed.
- [ ] 7.3 Implement `aca sync import` — import from file into current profile's database. Error if input file doesn't exist.
- [ ] 7.4 Implement `aca sync push` — orchestrate: file discovery → file sync → PG import → Neo4j sync. Enforce ordering; abort later stages if earlier stage fails.
- [ ] 7.5 Add `--pg-only` / `--neo4j-only` / `--files-only` flags for selective sync. Note: `--files-only` requires PG connection for file discovery (from source DB).
- [ ] 7.6 Add `--tables` flag for partial table sync (auto-includes FK parents with transitive closure)
- [ ] 7.7 Add `--dry-run` flag to preview sync operations without writing. Simulates FK remapping to detect issues. Reports per-table counts.
- [ ] 7.8 Register sync_commands in `src/cli/app.py`

## 8. Profile Integration (depends on: 7.1)

- [ ] 8.1 Add `resolve_profile_settings(profile_name)` helper in `src/config/settings.py` that loads a profile's YAML and resolves connection details (DATABASE_URL, NEO4J_URI, storage provider) without setting PROFILE env var globally. Return a `Settings` instance for the named profile.
- [ ] 8.2 Wire `--from-profile` / `--to-profile` flags in sync_commands to call `resolve_profile_settings()` for source and target
- [ ] 8.3 Validate: source and target must resolve to different DATABASE_URL and NEO4J_URI. Invalid profile name → error listing available profiles.

## 9. Incremental Sync (depends on: 7.*, 8.*)

- [ ] 9.1 Create Alembic migration for `sync_metadata` table: `id` (PK), `source_profile` (String), `target_profile` (String), `last_sync_timestamp` (DateTime), `tables_synced` (JSON), `record_count` (Integer), `status` (String). Unique constraint on `(source_profile, target_profile)`.
- [ ] 9.2 Implement `--since` flag for time-based filtering on export. Filter by `ingested_at` (contents), `created_at` (other tables). Include FK parents of filtered children regardless of date.
- [ ] 9.3 Auto-detect last sync timestamp: query `sync_metadata WHERE source_profile = ? AND target_profile = ? ORDER BY last_sync_timestamp DESC LIMIT 1`. Use as `--since` value.
- [ ] 9.4 Update `sync_metadata` on successful sync completion with new timestamp and record count.

## 10. Testing (depends on: respective implementation tasks)

Unit tests (can run in parallel):
- [ ] 10.1 Unit tests for pg_exporter — mock SQLAlchemy session, verify JSONL output format, topological ordering, streaming behavior (depends on: 2.*)
- [ ] 10.2 Unit tests for pg_importer — mock session, verify: natural-key dedup per table, FK remapping via IDMapper, self-referential FK two-pass, enum validation, merge/replace/clean modes, error accumulation (depends on: 3.*)
- [ ] 10.3 Unit tests for neo4j_exporter — mock Neo4j driver, verify node/relationship serialization (depends on: 4.*)
- [ ] 10.4 Unit tests for neo4j_importer — mock Neo4j driver, verify: MERGE idempotency (re-import = zero new nodes), clean mode (depends on: 5.*)
- [ ] 10.5 Unit tests for file_syncer — mock FileStorageService, verify: file discovery from DB, skip-existing logic, missing file warnings, bucket filtering (depends on: 6.*)
- [ ] 10.6 Unit tests for id_mapper — edge cases: self-referential FK deferred update, missing parent lookup, UUID mapping (depends on: 1.4)

Integration tests (sequential, after unit tests):
- [ ] 10.7 CLI tests for sync_commands — CliRunner with env isolation (`env={"PROFILE": ...}`), mock exporter/importer/syncer. Verify: `--yes` flag, `--dry-run` output, `--tables` auto-include message, error on invalid profile (depends on: 7.*)
- [ ] 10.8 Integration test: round-trip export → import with PostgreSQL test database (NOT SQLite — schema incompatibility with enums/FKs). Verify: (a) row counts match, (b) FK refs correctly remapped, (c) JSON fields survive round-trip, (d) enum values preserved, (e) self-referential FKs resolved (depends on: all Phase 1-4)

## 11. Documentation (can start after Phase 4)

- [ ] 11.1 Add sync commands to CLAUDE.md command reference
- [ ] 11.2 Update docs/SETUP.md with sync usage examples
- [ ] 11.3 Add sync section to docs/PROFILES.md (profile-based sync workflow)
