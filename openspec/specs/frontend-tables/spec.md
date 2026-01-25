# frontend-tables Specification

## Purpose
TBD - created by archiving change add-table-sorting. Update Purpose after archive.
## Requirements
### Requirement: Sortable Table Columns

The system SHALL provide sortable column headers for data tables displaying Content, Summary, Digest, Script, and Podcast records.

#### Scenario: User sorts by column ascending
- **WHEN** user clicks an unsorted column header
- **THEN** the table data is sorted by that column in ascending order
- **AND** an ascending arrow indicator is displayed in the column header
- **AND** the API is called with `sort_by={column}&sort_order=asc`

#### Scenario: User sorts by column descending
- **WHEN** user clicks a column header that is currently sorted ascending
- **THEN** the table data is sorted by that column in descending order
- **AND** a descending arrow indicator is displayed in the column header
- **AND** the API is called with `sort_by={column}&sort_order=desc`

#### Scenario: User clears sort
- **WHEN** user clicks a column header that is currently sorted descending
- **THEN** the table returns to default sort order
- **AND** no arrow indicator is displayed in any column header
- **AND** the API is called without sort parameters

#### Scenario: Sort with pagination resets to first page
- **WHEN** user changes the sort column or direction on a paginated table
- **THEN** the pagination resets to page 1 (or offset 0)
- **AND** results are fetched with the new sort parameters

### Requirement: Sort Indicator Visual Design

The system SHALL display clear visual indicators for sort state on column headers.

#### Scenario: Sortable column header appearance
- **WHEN** a table column supports sorting
- **THEN** the column header displays a hover effect (pointer cursor, highlight)
- **AND** the header includes space for a sort direction indicator

#### Scenario: Ascending sort indicator
- **WHEN** a column is sorted in ascending order
- **THEN** an upward-pointing arrow (▲ or equivalent icon) is displayed
- **AND** the arrow is positioned consistently with other sortable columns

#### Scenario: Descending sort indicator
- **WHEN** a column is sorted in descending order
- **THEN** a downward-pointing arrow (▼ or equivalent icon) is displayed

#### Scenario: Unsorted column appearance
- **WHEN** a column is not currently sorted but is sortable
- **THEN** no arrow indicator is displayed
- **AND** the column header still shows hover effects to indicate interactivity

### Requirement: Content Table Sorting

The Content table SHALL support sorting by user-visible columns.

#### Scenario: Sort Content by Title
- **WHEN** user clicks the Title column header
- **THEN** content items are sorted alphabetically by title

#### Scenario: Sort Content by Source Type
- **WHEN** user clicks the Source column header
- **THEN** content items are sorted by source type (gmail, rss, youtube, etc.)

#### Scenario: Sort Content by Publication
- **WHEN** user clicks the Publication column header
- **THEN** content items are sorted alphabetically by publication name

#### Scenario: Sort Content by Status
- **WHEN** user clicks the Status column header
- **THEN** content items are sorted by status value

#### Scenario: Sort Content by Published Date
- **WHEN** user clicks the Published Date column header
- **THEN** content items are sorted chronologically by publication date

#### Scenario: Sort Content by Ingested Date
- **WHEN** user clicks the Ingested Date column header
- **THEN** content items are sorted chronologically by ingestion timestamp
- **AND** this is the default sort order (descending)

### Requirement: Summary Table Sorting

The Summary table SHALL support sorting by user-visible columns.

#### Scenario: Sort Summary by Title
- **WHEN** user clicks the Title column header
- **THEN** summaries are sorted alphabetically by associated content title

#### Scenario: Sort Summary by Publication
- **WHEN** user clicks the Publication column header
- **THEN** summaries are sorted alphabetically by publication name

#### Scenario: Sort Summary by Model Used
- **WHEN** user clicks the Model Used column header
- **THEN** summaries are sorted alphabetically by model identifier

#### Scenario: Sort Summary by Created Date
- **WHEN** user clicks the Created Date column header
- **THEN** summaries are sorted chronologically by creation timestamp
- **AND** this is the default sort order (descending)

### Requirement: Digest Table Sorting

The Digest table SHALL support sorting by user-visible columns.

#### Scenario: Sort Digest by Type
- **WHEN** user clicks the Digest Type column header
- **THEN** digests are sorted by type (daily, weekly, sub_digest)

#### Scenario: Sort Digest by Period
- **WHEN** user clicks the Period column header
- **THEN** digests are sorted by period start date

#### Scenario: Sort Digest by Status
- **WHEN** user clicks the Status column header
- **THEN** digests are sorted by status value

#### Scenario: Sort Digest by Created Date
- **WHEN** user clicks the Created Date column header
- **THEN** digests are sorted chronologically by creation timestamp
- **AND** this is the default sort order (descending)

### Requirement: Script Table Sorting

The Script table SHALL support sorting by user-visible columns.

#### Scenario: Sort Script by Digest ID
- **WHEN** user clicks the Digest ID column header
- **THEN** scripts are sorted numerically by associated digest ID

#### Scenario: Sort Script by Status
- **WHEN** user clicks the Status column header
- **THEN** scripts are sorted by status value

#### Scenario: Sort Script by Created Date
- **WHEN** user clicks the Created Date column header
- **THEN** scripts are sorted chronologically by creation timestamp
- **AND** this is the default sort order (descending)

### Requirement: Podcast Table Sorting

The Podcast table SHALL support sorting by user-visible columns.

#### Scenario: Sort Podcast by Script ID
- **WHEN** user clicks the Script ID column header
- **THEN** podcasts are sorted numerically by associated script ID

#### Scenario: Sort Podcast by Duration
- **WHEN** user clicks the Duration column header
- **THEN** podcasts are sorted by duration in seconds

#### Scenario: Sort Podcast by File Size
- **WHEN** user clicks the File Size column header
- **THEN** podcasts are sorted by file size in bytes

#### Scenario: Sort Podcast by Status
- **WHEN** user clicks the Status column header
- **THEN** podcasts are sorted by status value

#### Scenario: Sort Podcast by Created Date
- **WHEN** user clicks the Created Date column header
- **THEN** podcasts are sorted chronologically by creation timestamp
- **AND** this is the default sort order (descending)

### Requirement: Backend Sort Parameter Validation

The API endpoints SHALL validate sort parameters and fall back to defaults for invalid values.

#### Scenario: Valid sort parameters
- **WHEN** API receives valid `sort_by` and `sort_order` parameters
- **THEN** results are returned sorted by the specified column and direction

#### Scenario: Invalid sort_by field
- **WHEN** API receives a `sort_by` value that is not in the allowed whitelist
- **THEN** the API uses the default sort column for that endpoint
- **AND** no error is returned to the client

#### Scenario: Invalid sort_order value
- **WHEN** API receives a `sort_order` value other than 'asc' or 'desc'
- **THEN** the API uses descending order as the default
- **AND** no error is returned to the client

#### Scenario: Missing sort parameters
- **WHEN** API receives a request without sort parameters
- **THEN** the API uses the endpoint's default sort (typically created_at DESC)
- **AND** behavior is identical to current implementation

### Requirement: Accessibility for Sortable Columns

Sortable table columns SHALL be accessible to screen readers and keyboard users.

#### Scenario: Screen reader announces sort state
- **WHEN** a sortable column header receives focus
- **THEN** the `aria-sort` attribute indicates current sort state (ascending, descending, or none)

#### Scenario: Keyboard activation
- **WHEN** user presses Enter or Space on a focused sortable column header
- **THEN** the sort action is triggered (same as mouse click)
