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

### Requirement: Sync-Safe File Handling

The system SHALL avoid reading partially synced files.

#### Scenario: File still syncing
- **GIVEN** a file's mtime/size is still changing during settle window
- **WHEN** polling occurs
- **THEN** the system SHALL defer ingestion until file stability is confirmed

### Requirement: Markdown Normalization

The system SHALL normalize Obsidian-specific markdown into ingest-compatible markdown.

#### Scenario: Obsidian constructs encountered
- **GIVEN** a note containing wikilinks, embeds, or callouts
- **WHEN** normalization runs
- **THEN** output markdown SHALL be produced for the standard parsing pipeline

### Requirement: Duplicate URL Behavior

The system SHALL deduplicate clips by canonical URL while preserving user context.

#### Scenario: URL clipped multiple times
- **GIVEN** two clip notes resolve to the same canonical URL
- **WHEN** ingestion runs
- **THEN** the system SHALL avoid duplicate primary content records
- **AND** preserve per-note metadata/annotations according to policy

### Requirement: Failure Recording and Replay

The system SHALL provide recoverable failure handling.

#### Scenario: Parse failure
- **GIVEN** malformed frontmatter or markdown
- **WHEN** ingestion fails
- **THEN** the failure reason SHALL be recorded
- **AND** the note SHALL be eligible for reprocessing after correction
