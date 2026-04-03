## ADDED Requirements

### Requirement: Obsidian sync CLI command
The system SHALL provide an `aca sync obsidian <vault-path>` command that exports the knowledge base as Obsidian-compatible markdown files.

#### Scenario: Basic export to empty vault
- **WHEN** `aca sync obsidian ./my-vault` is executed
- **AND** the vault directory does not exist
- **THEN** the directory SHALL be created
- **AND** digests, summaries, insights, content stubs, entities, and theme MOCs SHALL be written as markdown files
- **AND** a `.obsidian-sync-manifest.json` file SHALL be created in the vault root
- **AND** a summary table SHALL be displayed with columns: content type, created count, updated count, skipped count

#### Scenario: Export with Rich output
- **WHEN** `aca sync obsidian ./my-vault` is executed without `--json`
- **THEN** a Rich progress bar SHALL update once per exported item
- **AND** a Rich table SHALL display rows for each content type with columns: Type, Created, Updated, Skipped

#### Scenario: Export with JSON output
- **WHEN** `aca sync obsidian ./my-vault --json` is executed
- **THEN** output SHALL be a JSON object with keys: `digests`, `summaries`, `insights`, `content_stubs`, `entities`, `themes`, each containing `{"created": int, "updated": int, "skipped": int}`
- **AND** progress messages SHALL be sent to stderr

#### Scenario: Invalid vault path
- **WHEN** `aca sync obsidian /readonly/path` is executed
- **AND** the path is not writable
- **THEN** an error message SHALL indicate the path is not writable
- **AND** exit code SHALL be 1

#### Scenario: Vault path safety validation
- **WHEN** `aca sync obsidian <vault-path>` is executed
- **THEN** the system SHALL resolve the path to an absolute path using `Path.resolve()`
- **AND** the system SHALL reject paths that are symlinks to directories outside the user's home tree
- **AND** the system SHALL reject paths containing `..` traversal segments after resolution
- **AND** an error message SHALL indicate the path is unsafe if rejected

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
- **AND** the body SHALL list related entities as wikilinks under a "## Relationships" heading
- **AND** the body SHALL include entity facts under a "## Facts" heading

#### Scenario: Content hash format
- **WHEN** any note is exported
- **THEN** the `content_hash` frontmatter field SHALL be a SHA-256 hex digest string (64 characters), prefixed with `sha256:`
- **AND** the hash SHALL be computed from the full file content (frontmatter + body) excluding the `content_hash` field itself

#### Scenario: Tag sanitization in frontmatter
- **WHEN** a tag contains YAML-unsafe characters (colons, newlines, `---`, leading `#`)
- **THEN** the tag SHALL be sanitized by removing unsafe characters before inclusion in frontmatter
- **AND** empty tags after sanitization SHALL be omitted

### Requirement: Date-prefixed file naming
The system SHALL use date-prefixed, slugified filenames for all time-stamped content.

#### Scenario: Digest file naming
- **WHEN** a digest with title "Daily AI Digest" dated 2026-04-03 is exported
- **THEN** the filename SHALL be `2026-04-03-daily-ai-digest.md`

#### Scenario: Entity file naming
- **WHEN** an entity named "OpenAI" is exported
- **THEN** the filename SHALL be `OpenAI.md` (entities use name, not date prefix)

#### Scenario: Filename collision
- **WHEN** two items produce the same base filename
- **THEN** a numeric suffix SHALL be appended starting from 2 (e.g., `2026-04-03-ai-update-2.md`, `2026-04-03-ai-update-3.md`)
- **AND** the manifest SHALL track the actual filename used for each aca_id
- **AND** on subsequent runs, the manifest SHALL preserve the previously assigned filename to keep wikilinks stable

### Requirement: Related section with wikilinks
The system SHALL generate a "## Related" section at the end of each exported note by querying ContentReference relationships and converting them to Obsidian `[[wikilinks]]`.

#### Scenario: Related section generation
- **GIVEN** a content item has one or more ContentReference entries in the database
- **WHEN** the item is exported
- **THEN** a `## Related` heading SHALL appear at the end of the note body
- **AND** references SHALL be formatted as `- <ReferenceType>: [[<target-filename-without-extension>]]`
- **AND** reference types SHALL use title case labels: "Cites", "Extends", "Discusses", "Contradicts", "Supplements"

#### Scenario: Internal citation link
- **GIVEN** a summary S1 has a ContentReference of type CITES pointing to content C2
- **WHEN** S1 is exported
- **THEN** the Related section SHALL contain `- Cites: [[<C2-filename-without-extension>]]`

#### Scenario: Multiple reference types
- **GIVEN** a digest references multiple items with types CITES, EXTENDS, and DISCUSSES
- **WHEN** the digest is exported
- **THEN** each reference type SHALL appear as a labeled wikilink in the Related section

#### Scenario: External reference (resolved to external URL)
- **GIVEN** a ContentReference has resolution_status EXTERNAL with an external_url
- **WHEN** the referencing note is exported
- **THEN** the reference SHALL use a markdown link `- Cites: [<title>](<external_url>)` instead of a wikilink

#### Scenario: Unresolved reference
- **GIVEN** a ContentReference has resolution_status UNRESOLVED
- **WHEN** the referencing note is exported
- **THEN** the reference SHALL use a wikilink `- Cites: [[<slugified-title>]]`
- **AND** this creates a forward-link that Obsidian displays as an unresolved reference

#### Scenario: No references exist
- **GIVEN** a content item has no ContentReference entries
- **WHEN** the item is exported
- **THEN** no Related section SHALL be added to the note

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

#### Scenario: Corrupt manifest recovery
- **GIVEN** a `.obsidian-sync-manifest.json` file exists but contains invalid JSON
- **WHEN** `aca sync obsidian ./my-vault` is run
- **THEN** the corrupt manifest SHALL be renamed to `.obsidian-sync-manifest.json.bak`
- **AND** a new manifest SHALL be created
- **AND** a full re-export SHALL occur (all items treated as new)
- **AND** a warning SHALL be displayed indicating the manifest was rebuilt

#### Scenario: Atomic manifest writes
- **WHEN** the manifest is updated after an export
- **THEN** the system SHALL write to a temporary file first, then atomically rename to `.obsidian-sync-manifest.json`
- **AND** an incomplete write SHALL NOT corrupt the existing manifest

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
- **THEN** only time-stamped content (digests, summaries, insights, content stubs) dated on or after 2026-03-01 SHALL be exported
- **AND** entities SHALL be unaffected by `--since` (entities have no date dimension)
- **AND** theme MOCs SHALL be regenerated based on the filtered content set

#### Scenario: Content type exclusion
- **WHEN** `aca sync obsidian ./my-vault --no-entities --no-themes` is executed
- **THEN** the Entities/ and Themes/ folders SHALL not be created or updated
- **AND** other content types SHALL export normally

#### Scenario: Dry run
- **WHEN** `aca sync obsidian ./my-vault --dry-run` is executed
- **THEN** no files SHALL be written or deleted
- **AND** output SHALL list what WOULD be created, updated, or deleted

### Requirement: Structured logging
The system SHALL log export operations for debugging and audit purposes.

#### Scenario: Export action logging
- **WHEN** a file is created, updated, or skipped during export
- **THEN** a structured log entry SHALL be emitted at DEBUG level with fields: `aca_id`, `action` (created/updated/skipped), `filename`, `content_hash`

#### Scenario: Export summary logging
- **WHEN** an export completes
- **THEN** a structured log entry SHALL be emitted at INFO level with total counts per content type and elapsed time

### Requirement: Streaming database queries
The system SHALL use server-side cursors for database queries to avoid loading entire tables into memory.

#### Scenario: Large dataset export
- **WHEN** the database contains more than 1000 items of any content type
- **THEN** the exporter SHALL fetch items in batches of 500 using server-side cursors
- **AND** memory usage SHALL remain bounded regardless of total item count

### Requirement: Graceful Neo4j fallback
The system SHALL handle Neo4j being unavailable without failing the entire export.

#### Scenario: Neo4j unavailable
- **GIVEN** Neo4j is not running or not configured
- **WHEN** `aca sync obsidian ./my-vault` is executed
- **THEN** digests, summaries, insights, and content stubs SHALL still export
- **AND** a warning SHALL be printed to stderr: `WARNING: Neo4j unavailable; entity export skipped`
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
