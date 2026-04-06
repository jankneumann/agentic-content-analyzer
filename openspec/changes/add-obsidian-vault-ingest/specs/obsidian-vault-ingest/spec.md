# Obsidian Vault Ingest Capability

## ADDED Requirements

### Requirement: Vault Queue Ingestion

The system SHALL support ingesting captured web content from an Obsidian vault folder.

#### Scenario: New clip note appears
- **GIVEN** a configured vault ingest folder
- **WHEN** a new markdown clip note is synced into that folder
- **THEN** the system SHALL enqueue it for ingestion

#### Scenario: Idempotent processing
- **GIVEN** a previously ingested clip note
- **WHEN** the poller observes the same unchanged file again
- **THEN** the system SHALL NOT create duplicate content records

### Requirement: Frontmatter Contract

The system SHALL parse standardized clip metadata from frontmatter.

#### Scenario: Required metadata present
- **GIVEN** frontmatter includes `source_url` and `captured_at`
- **WHEN** ingestion runs
- **THEN** metadata SHALL be mapped to the internal content model

#### Scenario: Missing optional metadata
- **GIVEN** optional fields are absent
- **WHEN** ingestion runs
- **THEN** ingestion SHALL proceed with sensible defaults

#### Scenario: Missing required metadata
- **GIVEN** frontmatter is missing `source_url` or `captured_at`
- **WHEN** ingestion runs
- **THEN** the note SHALL be marked failed with `missing_required_metadata`

### Requirement: Sync-Safe File Handling

The system SHALL avoid reading partially synced files.

#### Scenario: File still syncing
- **GIVEN** a file's mtime/size is still changing during settle window
- **WHEN** polling occurs
- **THEN** the system SHALL defer ingestion until file stability is confirmed

#### Scenario: Temporary or lock file
- **GIVEN** a filename matches configured temp/lock patterns
- **WHEN** polling occurs
- **THEN** the system SHALL skip ingestion for that file

### Requirement: Markdown Normalization

The system SHALL normalize Obsidian-specific markdown into ingest-compatible markdown.

#### Scenario: Obsidian constructs encountered
- **GIVEN** a note containing wikilinks, embeds, or callouts
- **WHEN** normalization runs
- **THEN** output markdown SHALL be produced for the standard parsing pipeline

#### Scenario: Unsupported construct fallback
- **GIVEN** a note includes unsupported Obsidian syntax
- **WHEN** normalization runs
- **THEN** ingestion SHALL preserve readable fallback text instead of failing

### Requirement: Duplicate URL Behavior

The system SHALL deduplicate clips by canonical URL while preserving user context.

#### Scenario: URL clipped multiple times
- **GIVEN** two clip notes resolve to the same canonical URL
- **WHEN** ingestion runs
- **THEN** the system SHALL avoid duplicate primary content records
- **AND** preserve per-note metadata/annotations according to policy

#### Scenario: Canonicalization failure
- **GIVEN** URL canonicalization fails for a note
- **WHEN** ingestion runs
- **THEN** file-hash deduplication SHALL be used as fallback

### Requirement: Failure Recording and Replay

The system SHALL provide recoverable failure handling.

#### Scenario: Parse failure
- **GIVEN** malformed frontmatter or markdown
- **WHEN** ingestion fails
- **THEN** the failure reason SHALL be recorded
- **AND** the note SHALL be eligible for reprocessing after correction

#### Scenario: Retry after note correction
- **GIVEN** a previously failed note has changed
- **WHEN** polling detects a new hash/mtime
- **THEN** the system SHALL re-attempt ingestion automatically

### Requirement: Source Config Compatibility

The system SHALL safely stage configuration before `obsidian_ingest` runtime support is available.

#### Scenario: Template-only config in repository
- **GIVEN** `sources.d/obsidian-ingest.yaml.example` exists
- **WHEN** source configs are loaded
- **THEN** loader behavior SHALL remain unchanged because only `*.yaml` files are loaded

#### Scenario: Unsupported active source type
- **GIVEN** `sources.d/obsidian-ingest.yaml` is activated before `obsidian_ingest` type support exists
- **WHEN** source configs are loaded
- **THEN** validation SHALL fail explicitly and block startup until fixed

### Requirement: Path Safety

The system SHALL restrict vault access to allowed roots and reject traversal.

#### Scenario: Resolved path escapes allowed root
- **GIVEN** configured ingest path resolves outside an allowed vault root
- **WHEN** source config is validated
- **THEN** configuration SHALL be rejected with a clear error
