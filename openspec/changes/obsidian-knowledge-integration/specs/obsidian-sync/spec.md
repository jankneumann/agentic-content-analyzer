## ADDED Requirements

### Requirement: Obsidian sync CLI command
The system SHALL provide an `aca sync obsidian <vault-path>` command that exports the knowledge base as Obsidian-compatible markdown files.

#### Scenario: Basic export to empty vault
- **WHEN** `aca sync obsidian ./my-vault` is executed
- **AND** the vault directory does not exist
- **THEN** the directory SHALL be created
- **AND** digests, summaries, insights, content stubs, entities, and theme MOCs SHALL be written as markdown files
- **AND** a `.obsidian-sync-manifest.json` file SHALL be created in the vault root
- **AND** a summary of exported items SHALL be displayed

#### Scenario: Export with Rich output
- **WHEN** `aca sync obsidian ./my-vault` is executed without `--json`
- **THEN** progress SHALL be displayed using Rich progress bars
- **AND** a Rich table SHALL summarize counts per content type

#### Scenario: Export with JSON output
- **WHEN** `aca sync obsidian ./my-vault --json` is executed
- **THEN** output SHALL be valid JSON with counts per content type
- **AND** progress messages SHALL be sent to stderr

#### Scenario: Invalid vault path
- **WHEN** `aca sync obsidian /readonly/path` is executed
- **AND** the path is not writable
- **THEN** an error message SHALL indicate the path is not writable
- **AND** exit code SHALL be 1

### Requirement: Vault folder structure
The system SHALL organize exported files into typed subfolders within the vault path.

#### Scenario: Standard folder layout
- **WHEN** an export completes successfully
- **THEN** the vault SHALL contain these folders: `Digests/`, `Summaries/`, `Insights/`, `Content/`, `Entities/`, `Themes/`
- **AND** each folder SHALL only contain files of its respective type

#### Scenario: Empty content types
- **WHEN** no content exists for a given type (e.g., no insights)
- **THEN** the corresponding folder SHALL NOT be created
- **AND** no error SHALL be raised

### Requirement: YAML frontmatter
Every exported markdown file SHALL include YAML frontmatter with metadata that Obsidian can index.

#### Scenario: Digest frontmatter
- **WHEN** a digest is exported
- **THEN** the frontmatter SHALL include: `generator: aca`, `aca_id`, `aca_type: digest`, `date`, `tags`, `digest_type`, `period_start`, `period_end`, `content_hash`
- **AND** `tags` SHALL be a YAML list of theme tags extracted from the digest

#### Scenario: Summary frontmatter
- **WHEN** a summary is exported
- **THEN** the frontmatter SHALL include: `generator: aca`, `aca_id`, `aca_type: summary`, `date`, `tags`, `source_type`, `source_url`, `content_hash`

#### Scenario: Insight frontmatter
- **WHEN** an agent insight is exported
- **THEN** the frontmatter SHALL include: `generator: aca`, `aca_id`, `aca_type: insight`, `date`, `tags`, `insight_type`, `confidence`, `content_hash`

#### Scenario: Content stub frontmatter
- **WHEN** a content stub is exported
- **THEN** the frontmatter SHALL include: `generator: aca`, `aca_id`, `aca_type: content_stub`, `date`, `tags`, `source_type`, `source_url`, `author`, `publication`
- **AND** the body SHALL contain only the title, source URL link, and backlinks to summaries that reference it

#### Scenario: Entity frontmatter
- **WHEN** a knowledge graph entity is exported
- **THEN** the frontmatter SHALL include: `generator: aca`, `aca_id`, `aca_type: entity`, `entity_type`, `tags`
- **AND** the body SHALL list related entities as wikilinks and include fact summaries

### Requirement: Date-prefixed file naming
The system SHALL use date-prefixed, slugified filenames for all time-stamped content.

#### Scenario: Digest file naming
- **WHEN** a digest with title "Daily AI Digest" dated 2026-04-03 is exported
- **THEN** the filename SHALL be `2026-04-03-daily-ai-digest.md`

#### Scenario: Entity file naming
- **WHEN** an entity named "OpenAI" is exported
- **THEN** the filename SHALL be `OpenAI.md` (entities use name, not date prefix)

#### Scenario: Filename collision
- **WHEN** two items produce the same filename
- **THEN** a numeric suffix SHALL be appended (e.g., `2026-04-03-ai-update-2.md`)
- **AND** the manifest SHALL track the actual filename used

### Requirement: Wikilinks for cross-references
The system SHALL convert ContentReference relationships into Obsidian `[[wikilinks]]`.

#### Scenario: Internal citation link
- **GIVEN** a summary S1 has a ContentReference of type CITES pointing to content C2
- **WHEN** S1 is exported
- **THEN** a "Related" section SHALL appear at the end of the note
- **AND** it SHALL contain `- Cites: [[<C2-filename-without-extension>]]`

#### Scenario: Multiple reference types
- **GIVEN** a digest references multiple items with types CITES, EXTENDS, and DISCUSSES
- **WHEN** the digest is exported
- **THEN** each reference type SHALL appear as a labeled wikilink in the Related section

#### Scenario: Unresolved reference
- **GIVEN** a ContentReference has resolution_status UNRESOLVED or EXTERNAL
- **WHEN** the referencing note is exported
- **THEN** external references SHALL use a plain URL link instead of a wikilink
- **AND** unresolved references SHALL use a wikilink (Obsidian handles forward-links gracefully)

### Requirement: Theme Maps of Content
The system SHALL generate MOC (Map of Content) files that group notes by theme.

#### Scenario: MOC generation
- **WHEN** an export completes
- **THEN** for each unique theme tag across all exported notes, a `Themes/MOC - <Theme Name>.md` file SHALL be created
- **AND** the MOC SHALL contain wikilinks to all notes tagged with that theme
- **AND** links SHALL be grouped by content type (Digests, Summaries, Insights)

#### Scenario: MOC frontmatter
- **WHEN** a theme MOC is generated
- **THEN** its frontmatter SHALL include: `generator: aca`, `aca_type: moc`, `theme`, `note_count`

### Requirement: Incremental sync with manifest
The system SHALL track exported content in a manifest file and only write new or changed items on subsequent runs.

#### Scenario: First export creates manifest
- **WHEN** `aca sync obsidian ./my-vault` is run on an empty vault
- **THEN** a `.obsidian-sync-manifest.json` SHALL be created
- **AND** it SHALL contain an entry per exported file with: filename, aca_id, aca_type, content_hash, exported_at timestamp

#### Scenario: Incremental re-export skips unchanged
- **GIVEN** a vault with an existing manifest
- **WHEN** `aca sync obsidian ./my-vault` is run again
- **AND** no upstream content has changed
- **THEN** no files SHALL be overwritten
- **AND** the summary SHALL show 0 updated items

#### Scenario: Changed content is re-exported
- **GIVEN** a digest was previously exported with hash H1
- **AND** the digest has since been updated (new hash H2)
- **WHEN** `aca sync obsidian ./my-vault` is run
- **THEN** the digest file SHALL be overwritten with updated content
- **AND** the manifest entry SHALL update to hash H2

#### Scenario: Stale file cleanup
- **WHEN** `aca sync obsidian ./my-vault --clean` is executed
- **AND** a previously exported item no longer exists in the database
- **THEN** the corresponding managed file (with `generator: aca` frontmatter) SHALL be deleted
- **AND** the manifest entry SHALL be removed

#### Scenario: User-modified managed files
- **GIVEN** a user has edited a file that has `generator: aca` frontmatter
- **WHEN** `aca sync obsidian ./my-vault` is run
- **AND** the upstream content has also changed
- **THEN** the file SHALL be overwritten with the upstream version
- **AND** a warning SHALL be displayed listing files that had local modifications

### Requirement: Export filtering options
The system SHALL support CLI flags to filter what gets exported.

#### Scenario: Date filtering with --since
- **WHEN** `aca sync obsidian ./my-vault --since 2026-03-01` is executed
- **THEN** only content dated on or after 2026-03-01 SHALL be exported

#### Scenario: Content type exclusion
- **WHEN** `aca sync obsidian ./my-vault --no-entities --no-themes` is executed
- **THEN** the Entities/ and Themes/ folders SHALL not be created or updated
- **AND** other content types SHALL export normally

#### Scenario: Dry run
- **WHEN** `aca sync obsidian ./my-vault --dry-run` is executed
- **THEN** no files SHALL be written or deleted
- **AND** output SHALL list what WOULD be created, updated, or deleted

### Requirement: Graceful Neo4j fallback
The system SHALL handle Neo4j being unavailable without failing the entire export.

#### Scenario: Neo4j unavailable
- **GIVEN** Neo4j is not running or not configured
- **WHEN** `aca sync obsidian ./my-vault` is executed
- **THEN** digests, summaries, insights, and content stubs SHALL still export
- **AND** a warning SHALL indicate that entity export was skipped
- **AND** exit code SHALL be 0

### Requirement: MCP tool for Obsidian sync
The system SHALL expose an `sync_obsidian` MCP tool that allows agents and MCP clients to trigger vault exports programmatically.

#### Scenario: MCP tool basic export
- **WHEN** the `sync_obsidian` tool is called with `vault_path` argument
- **THEN** the ObsidianExporter SHALL run with the provided path
- **AND** the result SHALL be a JSON string with counts per content type (digests, summaries, insights, content_stubs, entities, themes)

#### Scenario: MCP tool with filtering options
- **WHEN** the `sync_obsidian` tool is called with `since`, `include_entities`, and `include_themes` arguments
- **THEN** the exporter SHALL respect these filters
- **AND** the result SHALL reflect only exported content types

#### Scenario: MCP tool error handling
- **WHEN** the `sync_obsidian` tool is called with an invalid vault path
- **THEN** a descriptive error message SHALL be returned as a JSON string
- **AND** the MCP server SHALL NOT crash

#### Scenario: Neo4j available
- **GIVEN** Neo4j is running and configured
- **WHEN** `aca sync obsidian ./my-vault` is executed
- **THEN** entities SHALL be exported to the Entities/ folder
- **AND** entity wikilinks SHALL appear in related notes
