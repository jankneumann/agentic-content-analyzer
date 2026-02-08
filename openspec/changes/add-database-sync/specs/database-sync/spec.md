## ADDED Requirements

### Requirement: Database Sync Export

The system SHALL provide a PostgreSQL export capability that serializes all application tables to a portable JSONL format, preserving relationships and metadata.

#### Scenario: Full export to file
- **GIVEN** a configured database profile with populated tables
- **WHEN** `aca sync export --output sync-data.jsonl` is executed
- **THEN** all application tables SHALL be exported to the specified file in JSONL format
- **AND** a manifest record SHALL be included with Alembic revision, export timestamp, and row counts per table
- **AND** tables SHALL be exported in topological order (parents before children)

#### Scenario: Filtered table export
- **GIVEN** a configured database profile
- **WHEN** `aca sync export --tables contents,summaries --output partial.jsonl` is executed
- **THEN** only the specified tables and their parent dependencies SHALL be exported
- **AND** any FK-referenced parent tables not in the list SHALL be automatically included

#### Scenario: Export progress reporting
- **WHEN** an export operation is running
- **THEN** the CLI SHALL display the current table name and row count as each table is exported
- **AND** a final summary SHALL show total rows exported and file size

### Requirement: Database Sync Import

The system SHALL provide a PostgreSQL import capability that deserializes JSONL exports into the target database, handling deduplication and FK remapping.

#### Scenario: Import with merge mode (default)
- **GIVEN** a JSONL export file and a target database with some existing data
- **WHEN** `aca sync import --input sync-data.jsonl` is executed
- **THEN** for each table, records SHALL be checked against their natural key: `content_hash` for contents, `(digest_type, period_start, period_end)` for digests, UUID for images/conversations/chat_messages, `key` for prompt_overrides, and `(remapped_fk, created_at)` for child tables (summaries, audio_digests, podcast_scripts, podcasts)
- **AND** records with matching natural keys SHALL be skipped
- **AND** new records SHALL be inserted with remapped FK references
- **AND** a summary SHALL show inserted, skipped, and failed counts per table

#### Scenario: Import with replace mode
- **GIVEN** a JSONL export file and a target database
- **WHEN** `aca sync import --input sync-data.jsonl --mode replace` is executed
- **THEN** existing records with matching natural keys SHALL be updated in place
- **AND** new records SHALL be inserted
- **AND** FK references SHALL be remapped to target database IDs

#### Scenario: Import with clean mode
- **GIVEN** a JSONL export file and a target database
- **WHEN** `aca sync import --input sync-data.jsonl --mode clean` is executed
- **THEN** a confirmation prompt SHALL be displayed before truncation
- **AND** all existing data in target tables SHALL be truncated (in reverse dependency order: Level 3 → 2 → 1 → 0)
- **AND** all records from the export SHALL be inserted in dependency order (Level 0 → 1 → 2 → 3)

#### Scenario: Import with clean mode non-interactive
- **GIVEN** a JSONL export file and a CI/CD or scripted environment
- **WHEN** `aca sync import --input sync-data.jsonl --mode clean --yes` is executed
- **THEN** the confirmation prompt SHALL be skipped
- **AND** truncation and import SHALL proceed immediately

#### Scenario: Schema version check — target behind source
- **GIVEN** an export file created at Alembic revision `abc123`
- **AND** the target database is at an older Alembic revision `older789`
- **WHEN** import is attempted
- **THEN** the import SHALL be blocked with an error message
- **AND** the error SHALL include the exact command to run: `PROFILE={target_profile} alembic upgrade head`
- **AND** no data SHALL be written to the target database

#### Scenario: Schema version check — target ahead of source
- **GIVEN** an export file created at Alembic revision `abc123`
- **AND** the target database is at a newer Alembic revision `newer456`
- **WHEN** import is attempted
- **THEN** the import SHALL proceed with a warning that the target schema is newer
- **AND** new nullable columns in the target SHALL receive default/NULL values

#### Scenario: Schema version check — revisions match
- **GIVEN** an export file and target database at the same Alembic revision
- **WHEN** import is attempted
- **THEN** the import SHALL proceed without warnings

#### Scenario: FK remapping during import
- **GIVEN** an export where Content id=42 has Summary with content_id=42
- **WHEN** Content is imported and receives new id=100 in the target database
- **THEN** the Summary's content_id SHALL be remapped to 100
- **AND** all FK relationships SHALL maintain referential integrity

#### Scenario: Self-referential FK remapping
- **GIVEN** an export where Content id=10 has canonical_id=5 (pointing to another Content)
- **WHEN** both Content id=10 and id=5 are imported
- **THEN** Content id=10 SHALL be inserted first with canonical_id=NULL
- **AND** after all contents are imported, canonical_id SHALL be updated to the remapped ID of Content 5
- **AND** if Content 5 was not in the export, canonical_id SHALL remain NULL with a warning logged

#### Scenario: Import error — missing FK parent
- **GIVEN** an export containing a Summary with content_id=42 but no Content with id=42
- **WHEN** import runs and the FK lookup fails
- **THEN** the Summary record SHALL be skipped with a warning: `Skipping summaries row: FK parent contents.id=42 not found in ID mapping`
- **AND** import SHALL continue with remaining records
- **AND** the error summary SHALL include the count of skipped records per table

#### Scenario: Import error — invalid enum value
- **GIVEN** an export containing a Content with source_type="unknown_source" not in the target schema
- **WHEN** import attempts to insert this record
- **THEN** the record SHALL be skipped with a warning: `Skipping contents row: invalid enum value 'unknown_source' for source_type`
- **AND** import SHALL continue with remaining records

#### Scenario: Import error — schema version blocked
- **GIVEN** an import that is blocked due to schema version mismatch
- **WHEN** the schema check fails before any data is written
- **THEN** no data SHALL be written to the target database (check runs within a transaction)
- **AND** the transaction SHALL be rolled back

### Requirement: Neo4j Knowledge Graph Sync

The system SHALL provide Neo4j export/import capability for the Graphiti knowledge graph, enabling sync between local and cloud Neo4j instances.

#### Scenario: Neo4j full export
- **GIVEN** a configured Neo4j connection with graph data
- **WHEN** `aca sync export --neo4j-only --output graph.jsonl` is executed
- **THEN** all Episode, Entity, and Relation nodes SHALL be exported
- **AND** all relationships between nodes SHALL be exported with source and target node references
- **AND** all node and relationship properties SHALL be preserved

#### Scenario: Neo4j import with merge mode
- **GIVEN** a Neo4j JSONL export and a target Neo4j instance
- **WHEN** `aca sync import --neo4j-only --input graph.jsonl` is executed
- **THEN** nodes SHALL be merged using UUID-based MERGE operations
- **AND** existing nodes with the same UUID SHALL not be duplicated
- **AND** relationships SHALL be created between merged nodes

#### Scenario: Neo4j import with clean mode
- **GIVEN** a Neo4j JSONL export and a target Neo4j instance
- **WHEN** `aca sync import --neo4j-only --input graph.jsonl --mode clean` is executed
- **THEN** all existing nodes and relationships SHALL be deleted
- **AND** all exported data SHALL be imported
- **AND** a message SHALL remind the user to run `graphiti.build_indices_and_constraints()` to rebuild indexes

### Requirement: File Storage Sync

The system SHALL provide file storage sync capability that copies files between storage providers (local, S3, Supabase Storage, Railway MinIO) using the unified `FileStorageService` interface, keyed by database file references.

#### Scenario: Full file sync between profiles
- **GIVEN** profiles `local` and `railway` are configured with different storage providers
- **WHEN** `aca sync push --from-profile local --to-profile railway --files-only` is executed
- **THEN** files referenced by Image, AudioDigest, and Podcast database records SHALL be copied from source to target storage
- **AND** files already existing on the target (by path) SHALL be skipped
- **AND** progress SHALL be reported per file (name, size, bucket)

#### Scenario: Selective bucket sync
- **GIVEN** a sync command with file storage included
- **WHEN** `aca sync push --from-profile local --to-profile railway --buckets images` is executed
- **THEN** only files in the `images` bucket SHALL be synced
- **AND** `podcasts` and `audio-digests` buckets SHALL be skipped

#### Scenario: File discovery from database references
- **GIVEN** the **source** database contains records with file path references
- **WHEN** file sync runs
- **THEN** the system SHALL query the source database for: `images.storage_path`, `audio_digests.audio_url`, and `podcasts.audio_url`
- **AND** only non-NULL file paths with database references SHALL be synced (no blind bucket enumeration)
- **AND** orphaned files without database references SHALL be ignored

#### Scenario: File sync with database sync
- **GIVEN** a full sync operation (no `--pg-only`, `--neo4j-only`, or `--files-only` flag)
- **WHEN** `aca sync push --from-profile local --to-profile railway` is executed
- **THEN** file paths SHALL be discovered from the **source** database first
- **AND** files SHALL be copied from source storage to target storage second
- **AND** PostgreSQL data SHALL be imported into the target database third
- **AND** Neo4j data SHALL be synced fourth

#### Scenario: Missing source file during file sync
- **GIVEN** a database record references a file path that does not exist in source storage
- **WHEN** file sync attempts to read the missing file
- **THEN** a warning SHALL be logged: `File not found in source storage: {path} (referenced by {table}.{column})`
- **AND** file sync SHALL continue with the remaining files
- **AND** the final summary SHALL include a count of missing files

### Requirement: Partial Table Sync

The system SHALL support syncing a subset of tables, automatically including FK parent dependencies.

#### Scenario: Sync contents and summaries only
- **GIVEN** a configured database with all tables populated
- **WHEN** `aca sync export --tables contents,summaries --output partial.jsonl` is executed
- **THEN** only `contents` and `summaries` tables SHALL be exported
- **AND** the `contents` table SHALL be exported first (as FK parent of summaries)

#### Scenario: Auto-include FK parents
- **GIVEN** a user requests `--tables summaries`
- **WHEN** the export runs
- **THEN** the `contents` table SHALL be auto-included because `summaries.content_id` references `contents.id`
- **AND** a message SHALL inform the user that `contents` was auto-included

#### Scenario: Partial import into populated database
- **GIVEN** a partial JSONL export (contents + summaries only)
- **AND** a target database with existing digests and images
- **WHEN** `aca sync import --input partial.jsonl` is executed
- **THEN** only contents and summaries SHALL be imported
- **AND** existing digests and images in the target database SHALL be untouched

### Requirement: Profile-Based Sync

The system SHALL support resolving source and target database connections from named profiles, enabling sync operations without manual connection string management.

#### Scenario: Push between profiles
- **GIVEN** profiles `local` and `railway` are configured
- **WHEN** `aca sync push --from-profile local --to-profile railway` is executed
- **THEN** data SHALL be exported from the `local` profile's database
- **AND** data SHALL be imported into the `railway` profile's database
- **AND** both PostgreSQL and Neo4j SHALL be synced (unless `--pg-only` or `--neo4j-only` specified)

#### Scenario: Profile validation — same database
- **GIVEN** a sync command with `--from-profile` and `--to-profile`
- **WHEN** both profiles resolve to the same `DATABASE_URL` or `NEO4J_URI`
- **THEN** the command SHALL abort with an error: `Source and target profiles resolve to the same database — aborting sync`

#### Scenario: Profile validation — invalid profile name
- **GIVEN** a sync command with `--from-profile nonexistent`
- **WHEN** the profile cannot be found in `profiles/` directory
- **THEN** the command SHALL abort with an error listing available profiles

#### Scenario: Current profile as default
- **GIVEN** the `PROFILE` environment variable is set to `local`
- **WHEN** `aca sync export --output data.jsonl` is executed without `--from-profile`
- **THEN** the active profile (`local`) SHALL be used as the source

### Requirement: Incremental Sync

The system SHALL support incremental sync based on timestamps, transferring only records created or modified since the last sync.

#### Scenario: Time-based export filter
- **GIVEN** a configured database with records spanning multiple dates
- **WHEN** `aca sync export --since "2026-02-01" --output recent.jsonl` is executed
- **THEN** only records with `ingested_at` or `created_at` >= the specified date SHALL be exported
- **AND** parent records referenced by FK from exported children SHALL be included regardless of date

#### Scenario: Auto-incremental sync
- **GIVEN** a `sync_metadata` table tracks the last successful sync timestamp
- **WHEN** `aca sync push --from-profile local --to-profile railway --incremental` is executed
- **THEN** only records newer than the last sync timestamp SHALL be exported
- **AND** the sync_metadata table SHALL be updated with the new sync timestamp on success

### Requirement: Sync Dry Run

The system SHALL support a dry-run mode that previews sync operations without modifying any data.

#### Scenario: Dry run preview
- **GIVEN** a JSONL export file and a target database
- **WHEN** `aca sync import --input data.jsonl --dry-run` is executed
- **THEN** the system SHALL report how many records would be inserted, skipped, and updated per table
- **AND** no database writes SHALL occur
- **AND** FK remapping SHALL be simulated to detect potential issues
