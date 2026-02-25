# Source Configuration: Web Search Sources

## MODIFIED Requirements

### Requirement: Supported Source Types

The system SHALL recognize `websearch` as a valid source type in `sources.d/` directory configuration.

#### Scenario: Loading websearch source file

- **WHEN** the source loader reads `sources.d/websearch.yaml`
- **THEN** each entry is parsed as a `WebSearchSource` with required fields: `name`, `provider`, `prompt`
- **AND** optional fields: `enabled` (default: true), `tags` (default: []), provider-specific overrides
- **AND** the `provider` field accepts values: `perplexity`, `grok`
- **AND** entries with unrecognized provider values are logged as warnings and skipped

#### Scenario: Websearch source defaults

- **WHEN** `sources.d/websearch.yaml` has a `defaults` section with `type: websearch` and `enabled: true`
- **THEN** all entries inherit the defaults unless explicitly overridden
- **AND** the cascading defaults pattern matches other source types (global defaults → file defaults → per-entry fields)

#### Scenario: Invalid websearch source entry

- **WHEN** a websearch source entry is missing the required `prompt` field or has an invalid `provider` value
- **THEN** the source loader logs a warning identifying the entry
- **AND** the entry is excluded from the loaded sources
- **AND** valid entries in the same file are still loaded

#### Scenario: Provider-specific source fields

- **WHEN** a websearch source entry includes provider-specific fields:
  - Perplexity: `max_results`, `recency_filter`, `context_size`, `domain_filter`
  - Grok: `max_threads`
- **THEN** these fields are passed to the respective provider's orchestrator function
- **AND** fields not applicable to the specified provider are ignored with a debug log

### Requirement: Source Directory Layout

The system SHALL include `websearch.yaml` as part of the standard `sources.d/` directory structure alongside existing source files.

#### Scenario: Complete source directory

- **WHEN** the source directory is listed
- **THEN** `websearch.yaml` appears alongside `_defaults.yaml`, `rss.yaml`, `youtube_playlist.yaml`, `youtube_rss.yaml`, `podcasts.yaml`, `gmail.yaml`, `substack.yaml`
- **AND** the file follows the same YAML structure pattern: `defaults` section + `sources` array
