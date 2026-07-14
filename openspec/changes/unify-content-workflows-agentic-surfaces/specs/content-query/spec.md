## MODIFIED Requirements

### Requirement: ContentQuery Model for Structured Content Selection

The system SHALL provide a `ContentQuery` model that encapsulates filter criteria for selecting content items across CLI, API, MCP, and frontend. All fields SHALL be optional, where `None` means no caller-supplied filter. Workflow callers SHALL normalize this query into a `SelectionPolicy` before execution.

Fields:
- `source_types`: list of `ContentSource` values
- `statuses`: list of `ContentStatus` values
- `publications`: list of exact publication names
- `publication_search`: ILIKE pattern for publication name
- `start_date`, `end_date`: half-open datetime range for workflow selection
- `date_basis`: `published_date` or `ingested_at`, defaulting to `published_date` for workflows
- `search`: title ILIKE pattern
- `limit`: positive integer cap on results
- `sort_by`: validated against `CONTENT_SORT_FIELDS`, defaulting to `published_date`
- `sort_order`: `asc` or `desc`, defaulting to `desc`
- `canonical_only`: whether alias rows are excluded, defaulting to true for workflows
- `require_summary`: whether a persisted summary is required, defaulting to true for theme, digest, and podcast workflows

#### Scenario: Filter content by source types
- **GIVEN** a ContentQuery with `source_types: [youtube, rss]`
- **WHEN** the query is resolved
- **THEN** only content with source type youtube or rss SHALL be returned

#### Scenario: Filter workflow content by date range
- **GIVEN** a ContentQuery with `start_date: 2026-02-20` and `end_date: 2026-02-25`
- **WHEN** the query is resolved for a workflow
- **THEN** only content with `2026-02-20 <= published_date < 2026-02-25` SHALL be eligible

#### Scenario: Filter content by status
- **GIVEN** a ContentQuery with `statuses: [pending, parsed]`
- **WHEN** the query is resolved
- **THEN** only content with matching status SHALL be returned

#### Scenario: Empty query matches operation defaults
- **GIVEN** a ContentQuery with no filters set
- **WHEN** the query is resolved for an operation
- **THEN** the operation's explicit default selection policy SHALL be applied

#### Scenario: Null and empty list treated the same
- **GIVEN** a ContentQuery with `source_types: []`
- **WHEN** the query is resolved
- **THEN** content of all source types SHALL be considered before operation defaults are applied

#### Scenario: Invalid source type rejected
- **GIVEN** a ContentQuery with `source_types: ["nonexistent_source"]`
- **WHEN** the query is submitted through any interface
- **THEN** validation SHALL fail with an error listing valid source types

#### Scenario: Invalid sort field rejected
- **GIVEN** a ContentQuery with `sort_by: "nonexistent_field"`
- **WHEN** the query is validated
- **THEN** validation SHALL fail with the valid fields from `CONTENT_SORT_FIELDS`

#### Scenario: Limit must be positive
- **GIVEN** a ContentQuery with `limit: 0` or `limit: -1`
- **WHEN** the query is validated
- **THEN** validation SHALL fail

## ADDED Requirements

### Requirement: ContentSetResolver for workflow execution

The system SHALL provide a `ContentSetResolver` that converts a normalized query and operation policy into a `ResolvedContentSet`. Preview and execution MUST use the same resolution logic, and execution MUST accept the resolved value rather than rebuilding the query.

#### Scenario: Preview fingerprint matches execution
- **WHEN** a caller previews a workflow query and then submits the unchanged normalized query
- **THEN** preview and execution produce the same selection fingerprint unless underlying content or summaries changed
- **AND** a mismatch is reported explicitly before generation starts

#### Scenario: Resolution diagnostics are structured
- **WHEN** candidate records are excluded during workflow resolution
- **THEN** the preview reports counts by exclusion reason
- **AND** it includes the eligible canonical content and summary counts
