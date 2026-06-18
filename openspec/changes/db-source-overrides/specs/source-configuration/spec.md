## ADDED Requirements

### Requirement: Database Source Overrides
The system SHALL support storing ingestion source definitions as database overrides in a dedicated `source_overrides` table, in addition to YAML files in `sources.d/`. Each override SHALL store the full source definition as validated JSON under a natural key, and SHALL be created, updated, listed, and deleted at runtime without editing YAML files. The override `config` SHALL be validated against the existing `Source` discriminated union (`BlogSource`, `RSSSource`, `YouTubePlaylistSource`, etc.) before being persisted; invalid configs SHALL be rejected.

#### Scenario: Add a net-new source override
- **WHEN** a caller adds a source with `type: blog` and `url: https://www.normaltech.ai/` that does not exist in YAML or the database
- **THEN** the system validates the config against `BlogSource`
- **AND** persists a new `source_overrides` row with `source_key: "blog:https://www.normaltech.ai/"`, `version: 1`, and `enabled: true`

#### Scenario: Update an existing source override (upsert)
- **WHEN** a caller adds or updates a source whose `source_key` already exists in `source_overrides`
- **THEN** the system updates the stored `config` in place and increments `version`
- **AND** does NOT create a duplicate row

#### Scenario: Reject an invalid source config
- **WHEN** a caller submits a `type: blog` source with no `url` field
- **THEN** the system rejects the request with a validation error
- **AND** no `source_overrides` row is created or modified

#### Scenario: Delete a source override
- **WHEN** a caller deletes a `source_key` that exists in `source_overrides`
- **THEN** the system removes the row
- **AND** subsequent source resolution no longer includes that database override

### Requirement: Natural-Key Source Identity
The system SHALL identify each source by a natural key of the form `<type>:<locator>`, where the locator is the source's primary identifier for its type: `url` for `blog`, `rss`, `substack`, `podcast`, `youtube_rss`; `id` for `youtube_playlist`; `channel_id` for `youtube_channel`; `query` for `gmail`, `scholar`. This key SHALL determine union-vs-update on write and SHALL align a database override with its YAML twin (a source with the same key) for merge resolution.

#### Scenario: Database source matches a YAML source by key
- **WHEN** `sources.d/blogs.yaml` defines a blog with `url: https://www.together.ai/blog` AND a `source_overrides` row exists with the same `source_key`
- **THEN** the two are treated as the same logical source during merge
- **AND** the database override takes precedence over the YAML definition

#### Scenario: Locator derived per source type
- **WHEN** a `youtube_playlist` source override is created with `id: PLxxxx`
- **THEN** its `source_key` is `"youtube_playlist:PLxxxx"`

### Requirement: Source Resolution Precedence and Merge
The system SHALL merge database source overrides on top of YAML-defined sources inside `load_sources_config()`, the single resolution point all ingestion consumers use. Database overrides SHALL take precedence over YAML sources with the same natural key. A database override with `enabled: false` SHALL suppress (shadow) its YAML twin so that the source is excluded from ingestion. Each resolved source SHALL expose its `origin` as `yaml` or `db`. The merge SHALL fail open: if the database is unavailable or the lookup errors, the system SHALL return the YAML-only configuration and log at debug level.

#### Scenario: Database override adds a source to the resolved set
- **WHEN** a `source_overrides` row exists for `blog:https://www.normaltech.ai/` with `enabled: true` and no YAML twin
- **THEN** `load_sources_config()` includes that blog in the resolved sources with `origin: db`
- **AND** the next blog ingest scrapes it without any YAML change

#### Scenario: Database override disables a YAML source
- **WHEN** a YAML blog `https://www.together.ai/blog` exists AND a `source_overrides` row for the same key has `enabled: false`
- **THEN** the resolved configuration excludes that blog from ingestion

#### Scenario: Database override edits a YAML source
- **WHEN** a YAML blog and a `source_overrides` row share a key but the override changes `max_entries` and `link_selector`
- **THEN** the resolved source uses the database override's field values with `origin: db`

#### Scenario: Database unavailable — fail open to YAML
- **WHEN** `load_sources_config()` runs and the database lookup raises (e.g. during CLI without a database, or startup)
- **THEN** the system returns the YAML-only configuration
- **AND** logs the failure at debug level without raising

### Requirement: Source Override Management API
The system SHALL expose admin-authenticated HTTP endpoints under `/api/v1/sources` to list, add/update, delete, and enable/disable source overrides. The list endpoint SHALL report each source's `origin` (`yaml` | `db`) and `enabled` state. Write endpoints SHALL validate the source config against the source union and SHALL return the resulting key, version, and origin.

#### Scenario: List sources with origin
- **WHEN** a client requests the source list
- **THEN** the response includes both YAML-defined and database-defined sources, each tagged with `origin` and `enabled`

#### Scenario: Add a source via API
- **WHEN** an admin-authenticated client POSTs a valid `type: blog` source
- **THEN** the system upserts a `source_overrides` row and returns its `source_key`, `version`, and `origin: db`

#### Scenario: Reject unauthenticated write
- **WHEN** a client without a valid admin key attempts to add, update, delete, or toggle a source
- **THEN** the system rejects the request as unauthorized

#### Scenario: Enable/disable a source via API
- **WHEN** an admin-authenticated client toggles a source's `enabled` flag
- **THEN** the system persists the new `enabled` value (creating a disable-shadow row if the target is a YAML source)

### Requirement: Source Override CLI
The system SHALL provide CLI commands `aca sources list`, `aca sources add`, `aca sources remove`, `aca sources enable`, and `aca sources disable` to manage source overrides. The commands SHALL operate in dual mode: calling the HTTP API when a backend is available and falling back to direct database access otherwise, mirroring `aca settings`.

#### Scenario: Add a blog source from the CLI
- **WHEN** a user runs `aca sources add blog --url https://www.normaltech.ai/ --name "Normal Tech"`
- **THEN** the system validates and upserts the source override
- **AND** reports the resulting `source_key` and version

#### Scenario: List sources from the CLI shows origin
- **WHEN** a user runs `aca sources list`
- **THEN** the output shows each source's type, key, enabled state, and origin (`yaml` | `db`)

#### Scenario: Disable a YAML source from the CLI
- **WHEN** a user runs `aca sources disable blog:https://www.together.ai/blog`
- **THEN** the system records a disable-shadow override so the source is excluded from ingestion

### Requirement: Source Override Web UI
The web application SHALL provide a `/settings/sources` page that lists configured sources grouped by type, showing origin and enabled badges, and SHALL allow adding a source (with the full per-type field set), toggling enabled state, and deleting database-origin sources. The UI SHALL mirror the existing model-configuration settings pattern.

#### Scenario: Add a source from the UI
- **WHEN** a user opens the add-source dialog, selects `blog`, enters `https://www.normaltech.ai/`, and saves
- **THEN** the UI calls the add endpoint and the new source appears in the list with `origin: db`

#### Scenario: Delete control limited to database-origin sources
- **WHEN** the sources list renders a YAML-origin source
- **THEN** the UI offers disable (shadow) but not hard delete for that source
- **AND** database-origin sources offer delete
