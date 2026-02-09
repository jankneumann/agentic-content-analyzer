# Change: Add Database Sync Between Local and Cloud Environments

## Why

When switching between database providers (local Docker ↔ Railway/Supabase/Neon for PostgreSQL, local Docker ↔ AuraDB for Neo4j), the data in each environment drifts apart. Currently, the only way to populate a new environment is to re-ingest all content from scratch — a slow, API-rate-limited process that also loses processed state (summaries, digests, theme analyses). A sync mechanism would allow keeping environments aligned without full re-ingestion, enabling seamless transitions between local development and cloud deployments.

## What Changes

- **New `aca sync` CLI command group** with subcommands for PostgreSQL and Neo4j sync operations
- **New `src/sync/` module** implementing profile-aware export/import with format conversion
- **PostgreSQL sync**: Export all tables (contents, summaries, digests, images, themes, audio_digests, podcasts, jobs) to a portable JSONL format, import into target database preserving relationships and deduplication
- **Neo4j sync**: Export knowledge graph entries (episodes, entities, relationships) via Cypher queries, import into target Neo4j instance; indexes/constraints rebuilt separately via Graphiti
- **File storage sync**: Copy files (images, podcasts, audio-digests) between storage providers (local ↔ S3/Supabase Storage/Railway MinIO) using the unified `FileStorageProvider` interface, keyed by database file references
- **Partial table sync**: Support `--tables contents,summaries` for syncing only the most critical tables; auto-includes FK parent dependencies
- **Profile-aware source/target resolution**: Sync commands resolve connection details from profile configuration, supporting `--from-profile` and `--to-profile` flags
- **Incremental sync support**: Track sync timestamps to only transfer new/modified records on subsequent syncs
- **Conflict resolution**: Handle ID collisions and natural-key deduplication (content_hash for contents, composite keys for child tables) when merging data across environments
- **Error resilience**: Non-fatal handling of missing FK parents, unknown enum values, and missing source files — import continues with warnings rather than aborting

## Impact

- Affected specs: `database-provider` (MODIFIED — adds sync capability), new `database-sync` capability
- Affected code:
  - New: `src/sync/` (exporter, importer, file sync, format handling)
  - New: `src/cli/sync_commands.py` (CLI interface)
  - Modified: `src/config/settings.py` (sync-related settings)
  - Modified: profiles (optional sync settings)
- **No breaking changes** — purely additive feature
- **One small migration** — optional `sync_metadata` table for incremental sync tracking
