# Content Query Builder Spec Delta

## ADDED Requirements

### Requirement: ContentQuery Model for Structured Content Selection

The system SHALL provide a `ContentQuery` model that encapsulates filter criteria for selecting content items across CLI, API, and frontend. All fields SHALL be optional (None means "no filter").

#### Scenario: Filter content by source types
- **GIVEN** a ContentQuery with `source_types: [youtube, rss]`
- **WHEN** the query is resolved
- **THEN** only content with source_type youtube or rss SHALL be returned

#### Scenario: Filter content by date range
- **GIVEN** a ContentQuery with `start_date: 2026-02-20` and `end_date: 2026-02-25`
- **WHEN** the query is resolved
- **THEN** only content published within that date range SHALL be returned

#### Scenario: Filter content by status
- **GIVEN** a ContentQuery with `statuses: [pending, parsed]`
- **WHEN** the query is resolved
- **THEN** only content with matching status SHALL be returned

#### Scenario: Empty query matches all content
- **GIVEN** a ContentQuery with no filters set
- **WHEN** the query is resolved directly (not via an operation)
- **THEN** all content items SHALL be returned (subject to limit)

#### Scenario: Null and empty list treated the same
- **GIVEN** a ContentQuery with `source_types: []`
- **WHEN** the query is resolved
- **THEN** content of ALL source types SHALL be returned (same as `source_types: null`)

#### Scenario: Invalid source type rejected
- **GIVEN** a ContentQuery with `source_types: ["nonexistent_source"]`
- **WHEN** the query is submitted via API
- **THEN** the system SHALL return HTTP 400 with error listing valid source types

#### Scenario: Invalid sort_by field rejected
- **GIVEN** a ContentQuery with `sort_by: "nonexistent_field"`
- **WHEN** the query is validated
- **THEN** the system SHALL return an error listing valid sort fields from CONTENT_SORT_FIELDS

#### Scenario: Limit must be positive
- **GIVEN** a ContentQuery with `limit: 0` or `limit: -1`
- **WHEN** the query is validated
- **THEN** the system SHALL reject the query with a validation error

### Requirement: Query Preview (Dry-Run) Without Execution

The system SHALL support previewing what content matches a query without executing any batch operation. Preview SHALL return count, breakdowns, and sample titles.

#### Scenario: Preview returns count and breakdown
- **GIVEN** a ContentQuery with filters matching 23 content items
- **WHEN** a preview is requested
- **THEN** the system SHALL return total_count=23, by_source breakdown (alphabetical), by_status breakdown (alphabetical), date_range, and up to 10 sample_titles (most recent first)
- **AND** no content SHALL be modified or processed

#### Scenario: Preview with zero matches
- **GIVEN** a ContentQuery with filters that match no content
- **WHEN** a preview is requested
- **THEN** the system SHALL return total_count=0, empty by_source, empty by_status, null date_range values, empty sample_titles
- **AND** HTTP status SHALL be 200 (not 204 or error)

#### Scenario: CLI dry-run flag
- **GIVEN** the CLI command `aca summarize pending --source youtube --dry-run`
- **WHEN** executed
- **THEN** the system SHALL display a Rich table showing matching items count, source/status breakdown, and sample titles
- **AND** no summarization SHALL be performed
- **AND** exit code SHALL be 0

#### Scenario: API dry-run returns preview
- **GIVEN** a POST to `/api/v1/contents/summarize` with `dry_run: true` and `query` field
- **WHEN** the request is processed
- **THEN** the system SHALL return ContentQueryPreview in the response body (HTTP 200)
- **AND** no summarization jobs SHALL be enqueued

### Requirement: Operation-Specific Default Statuses

When a ContentQuery is passed to an operation without explicit statuses, each operation SHALL apply its own default.

#### Scenario: Summarizer defaults to PENDING and PARSED
- **GIVEN** a ContentQuery with `source_types: [youtube]` and `statuses: null`
- **WHEN** passed to summarize_pending_contents
- **THEN** the system SHALL filter by `statuses: [PENDING, PARSED]` AND `source_types: [youtube]`

#### Scenario: Digest defaults to COMPLETED
- **GIVEN** a ContentQuery with `source_types: [gmail]` and `statuses: null`
- **WHEN** passed to DigestCreator via DigestRequest.content_query
- **THEN** the system SHALL filter by `statuses: [COMPLETED]` AND `source_types: [gmail]`

#### Scenario: Explicit statuses override defaults
- **GIVEN** a ContentQuery with `statuses: [parsed, completed]`
- **WHEN** passed to summarize_pending_contents
- **THEN** the system SHALL use the explicit statuses, NOT the defaults

### Requirement: CLI Filter Options on Summarize Command

The `aca summarize pending` command SHALL accept optional filter options to target specific content.

#### Scenario: Summarize with source filter
- **GIVEN** the command `aca summarize pending --source youtube,rss`
- **WHEN** executed
- **THEN** only youtube and rss content with pending/parsed status SHALL be summarized

#### Scenario: Summarize with date filter
- **GIVEN** the command `aca summarize pending --after 2026-02-20`
- **WHEN** executed
- **THEN** only content published after 2026-02-20 with pending/parsed status SHALL be summarized

#### Scenario: Default behavior unchanged
- **GIVEN** the command `aca summarize pending` with no filter options
- **WHEN** executed
- **THEN** all pending/parsed content SHALL be summarized (identical to pre-change behavior)

#### Scenario: Invalid source value exits with error
- **GIVEN** the command `aca summarize pending --source youtube,invalid_source`
- **WHEN** executed
- **THEN** the system SHALL print an error message listing valid source types
- **AND** exit code SHALL be 1
- **AND** no summarization SHALL be started

#### Scenario: Invalid date format exits with error
- **GIVEN** the command `aca summarize pending --after "not-a-date"`
- **WHEN** executed
- **THEN** the system SHALL print an error message with format hint (YYYY-MM-DD)
- **AND** exit code SHALL be 1

### Requirement: CLI Filter Options on Digest Command

The `aca create-digest` command SHALL accept optional filter options to control which content is included.

#### Scenario: Digest with source filter
- **GIVEN** the command `aca create-digest daily --source gmail,rss`
- **WHEN** executed
- **THEN** only gmail and rss content with COMPLETED status SHALL be included in the digest

#### Scenario: Digest dry-run
- **GIVEN** the command `aca create-digest daily --source gmail --dry-run`
- **WHEN** executed
- **THEN** a preview of matching content SHALL be displayed
- **AND** no digest SHALL be generated

#### Scenario: Digest content_query merge with period dates
- **GIVEN** a DigestRequest with `period_start=2026-02-20`, `period_end=2026-02-25`, and `content_query` with `source_types: [youtube]` but no start_date/end_date
- **WHEN** the digest is generated
- **THEN** the system SHALL use period_start and period_end as date filters AND filter by youtube source

### Requirement: API Query Endpoints

The API SHALL expose a preview endpoint and extend existing summarize/digest endpoints to accept query filters.

#### Scenario: Preview endpoint
- **GIVEN** a POST request to `/api/v1/contents/query/preview` with a ContentQuery body
- **WHEN** the request is processed
- **THEN** a ContentQueryPreview response SHALL be returned (HTTP 200) with count and breakdown

#### Scenario: Preview endpoint with invalid input
- **GIVEN** a POST request to `/api/v1/contents/query/preview` with invalid `source_types: ["bad"]`
- **WHEN** the request is processed
- **THEN** the system SHALL return HTTP 400 with validation error details

#### Scenario: Summarize with query filter
- **GIVEN** a POST request to `/api/v1/contents/summarize` with a `query` field
- **WHEN** the request is processed
- **THEN** only content matching the query SHALL be summarized

#### Scenario: Summarize with both content_ids and query
- **GIVEN** a POST to `/api/v1/contents/summarize` with `content_ids: [1,2,3]` and `query: {source_types: ["youtube"]}`
- **WHEN** the request is processed
- **THEN** the system SHALL use the `query` field and ignore `content_ids`

#### Scenario: Digest generate with content query
- **GIVEN** a POST request to `/api/v1/digests/generate` with a `content_query` field
- **WHEN** the request is processed
- **THEN** only content matching the query SHALL be included in the digest

#### Scenario: Digest generate dry-run
- **GIVEN** a POST to `/api/v1/digests/generate` with `dry_run: true` and `content_query` field
- **WHEN** the request is processed
- **THEN** the system SHALL return ContentQueryPreview (HTTP 200)
- **AND** no digest SHALL be generated

### Requirement: Frontend Query Builder Component

The frontend SHALL provide a composable query builder component for batch operations.

#### Scenario: Filter chips UI
- **GIVEN** the query builder is rendered
- **WHEN** the user adds a source filter
- **THEN** a filter chip SHALL appear showing the selected source
- **AND** the chip SHALL have a remove button

#### Scenario: Live preview count update
- **GIVEN** the query builder has active filters
- **WHEN** filters change
- **THEN** the preview count SHALL update (debounced, staleTime 2s)
- **AND** a loading indicator SHALL be shown during the API call

#### Scenario: Preview error handling
- **GIVEN** the query builder has active filters
- **WHEN** the preview API returns an error
- **THEN** the system SHALL display an error message with a "Retry" button
- **AND** the previous preview data SHALL be retained

#### Scenario: Summarize dialog integration
- **GIVEN** the summarize dialog is open with query builder showing 23 matching items
- **WHEN** the user clicks "Summarize 23 items"
- **THEN** only the 23 matching content items SHALL be submitted for summarization

### Requirement: Backward Compatibility

All existing commands and API endpoints SHALL continue to work identically without any filter parameters.

#### Scenario: Existing summarize pending
- **GIVEN** the command `aca summarize pending` or API call without query field
- **WHEN** executed
- **THEN** behavior SHALL be identical to pre-change behavior

#### Scenario: Existing digest generation
- **GIVEN** the command `aca create-digest daily` or API call without content_query field
- **WHEN** executed
- **THEN** behavior SHALL be identical to pre-change behavior

#### Scenario: Existing content listing API
- **GIVEN** a GET request to `/api/v1/contents` with existing query parameters
- **WHEN** processed after the ContentQueryService refactoring
- **THEN** the response SHALL be identical to the pre-refactoring response
