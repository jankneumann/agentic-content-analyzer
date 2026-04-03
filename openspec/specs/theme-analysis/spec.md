# theme-analysis Specification

## Purpose
TBD - created by archiving change persist-theme-analysis. Update Purpose after archive.
## Requirements
### Requirement: Theme analysis results persist to PostgreSQL
The system SHALL store all theme analysis results in the `theme_analyses` PostgreSQL table. Results MUST survive API restarts and be queryable by date range, status, and recency.

#### Scenario: Analysis result persisted after completion
- **WHEN** a theme analysis background task completes successfully
- **THEN** a `ThemeAnalysis` record with `status=completed` SHALL exist in the database containing all themes, scores, and metadata

#### Scenario: Failed analysis records error
- **WHEN** a theme analysis background task fails
- **THEN** the `ThemeAnalysis` record SHALL have `status=failed` and `error_message` populated with the error description (truncated to 1000 chars)

#### Scenario: Data survives API restart
- **WHEN** the API server is restarted after a completed analysis
- **THEN** `GET /api/v1/themes/latest` SHALL return the most recent completed analysis from the database

### Requirement: Theme analysis lifecycle tracked via status column
The system SHALL track the lifecycle of each analysis via an `AnalysisStatus` enum with values: `queued`, `running`, `completed`, `failed`. Status transitions MUST follow the sequence: `queued` → `running` → `completed` or `failed`.

#### Scenario: Initial record created with queued status
- **WHEN** `POST /api/v1/themes/analyze` is called
- **THEN** a `ThemeAnalysis` record SHALL be created with `status=queued` and placeholder values before the background task starts

#### Scenario: Status transitions to running
- **WHEN** the background task begins processing
- **THEN** the record's status SHALL be updated to `running`

#### Scenario: Status transitions to completed on success
- **WHEN** the background task finishes successfully
- **THEN** the record's status SHALL be updated to `completed` with all result fields populated

### Requirement: Legacy newsletter field names renamed to content
The `ThemeAnalysis` ORM model and `ThemeAnalysisResult` Pydantic model SHALL use `content_count` and `content_ids` instead of `newsletter_count` and `newsletter_ids`. The API response SHALL use `content_count` and `content_ids`. No backward compatibility mapping is required.

#### Scenario: ORM model uses content naming
- **WHEN** a `ThemeAnalysis` record is created
- **THEN** the columns SHALL be named `content_count` and `content_ids`

#### Scenario: API response uses content naming
- **WHEN** `GET /api/v1/themes/latest` returns a completed analysis
- **THEN** the response JSON SHALL contain `content_count` and `content_ids` fields (not `newsletter_count`/`newsletter_ids`)

### Requirement: Analysis results list with pagination
The `GET /api/v1/themes` endpoint SHALL return a paginated list of past analyses ordered by `created_at` descending. It MUST support `limit` and `offset` query parameters.

#### Scenario: List returns all past analyses
- **WHEN** `GET /api/v1/themes?limit=10&offset=0` is called
- **THEN** the response SHALL be a JSON array of analysis summaries with `id`, `status`, `total_themes`, `analysis_date`, `start_date`, `end_date`, and `content_count`

#### Scenario: Pagination via offset
- **WHEN** 15 analyses exist and `GET /api/v1/themes?limit=10&offset=10` is called
- **THEN** the response SHALL contain 5 analysis summaries

### Requirement: Individual analysis retrievable by ID
The `GET /api/v1/themes/analysis/{analysis_id}` endpoint SHALL return the full analysis result from the database when the analysis is completed, or just the status when still running.

#### Scenario: Completed analysis returns full result
- **WHEN** `GET /api/v1/themes/analysis/{id}` is called for a completed analysis
- **THEN** the response SHALL contain `status: "completed"` and a full `result` object with all themes and metadata

#### Scenario: Non-existent analysis returns 404
- **WHEN** `GET /api/v1/themes/analysis/99999` is called
- **THEN** the response SHALL be HTTP 404 with detail "Analysis 99999 not found"

### Requirement: Completed analysis written to Neo4j as Graphiti episode
The system SHALL write each completed theme analysis to Neo4j via `GraphitiClient.add_episode()`. The episode body MUST contain a structured markdown summary of the themes, their categories, trends, and key points so that Graphiti can auto-extract theme entities and relationships for temporal evolution queries.

#### Scenario: Analysis episode added to knowledge graph
- **WHEN** a theme analysis completes successfully
- **THEN** a Graphiti episode SHALL be added with `reference_time` set to the analysis date and `source_description` indicating it is a theme analysis result

#### Scenario: Future analysis can query past theme episodes
- **WHEN** a new theme analysis runs after a previous analysis has been written to Neo4j
- **THEN** the historical context analyzer SHALL be able to discover the previous analysis themes via semantic search on the knowledge graph

### Requirement: Cross-theme insights stored in database
The `ThemeAnalysis` model SHALL include a `cross_theme_insights` JSON column to store the list of cross-theme insight strings generated by the LLM. This column SHALL be nullable for backward compatibility with analyses that don't generate insights.

#### Scenario: Insights persisted with analysis
- **WHEN** a theme analysis completes with cross-theme insights
- **THEN** the `cross_theme_insights` column SHALL contain the list of insight strings

### Requirement: Broken Alembic merge migrations fixed
The broken merge migrations `85939732a918` and `a23a53ea737b` SHALL be deleted and replaced with a single valid merge migration that produces a single Alembic head.

#### Scenario: Single Alembic head after fix
- **WHEN** `python scripts/check_alembic_heads.py` is run
- **THEN** it SHALL report exactly one head

#### Scenario: Migration upgrade succeeds
- **WHEN** `alembic upgrade head` is run against the database
- **THEN** the `theme_analyses` table SHALL be created with all required columns and indexes

### Requirement: Database Persistence

The theme analysis pipeline MUST persist results to a PostgreSQL `theme_analyses` table.

#### Scenario: theme-analysis.1 — Table creation

**MUST** create the `theme_analyses` table with all columns defined in `ThemeAnalysis` ORM model.
**MUST** create the `analysisstatus` PG enum with values: queued, running, completed, failed.
**MUST** apply cleanly via `alembic upgrade head` on a database that already has the no-op migration applied.
**SHALL** include proper downgrade (drop table, drop enum).

### Requirement: Table View

The themes page MUST provide a sortable, filterable table view of analysis results.

#### Scenario: theme-analysis.2 — Table rendering and interaction

**MUST** display all themes from the current analysis in a sortable table.
**MUST** support sorting by: name, category, trend, relevance_score, strategic_relevance, tactical_relevance, mention_count.
**MUST** support filtering by category and trend.
**SHALL** expand to show full details (description, key_points, historical_context, related_themes) on row click.
**MUST** show "No themes" empty state when analysis has zero themes.

### Requirement: Network Graph View

The themes page MUST provide an interactive force-directed graph of theme relationships.

#### Scenario: theme-analysis.3 — Network graph rendering

**MUST** render themes as nodes in a force-directed graph.
**MUST** size nodes by relevance_score.
**MUST** color nodes by category.
**MUST** draw edges from related_themes relationships.
**SHALL** show tooltip on hover with theme name, category, trend, relevance score.
**SHALL** highlight connected nodes on click.
**MUST** show empty state when no themes or no relationships exist.

### Requirement: Timeline Chart View

The themes page MUST visualize theme evolution over time as a horizontal range chart.

#### Scenario: theme-analysis.4 — Timeline rendering

**MUST** render themes as horizontal bars spanning first_seen to last_seen.
**MUST** color bars by category.
**SHALL** indicate trend visually (icon or label on bar).
**MUST** sort themes by first_seen date on Y-axis.
**MUST** show empty state when no themes exist.

### Requirement: View Toggle

The themes page MUST allow switching between cards, table, and graph views.

#### Scenario: theme-analysis.5 — View switching

**MUST** toggle between cards (default), table, and graph views via toolbar buttons.
**MUST** visually indicate the active view.
**MUST** preserve view state when analysis data refreshes.
**SHALL** default to "cards" view on initial page load.

### Requirement: Graph View Tabs

The graph view MUST provide Network and Timeline tabs for sub-navigation.

#### Scenario: theme-analysis.6 — Graph tab navigation

**MUST** provide Network and Timeline tabs within the Graph View.
**SHALL** default to Network tab.
**MUST** preserve tab selection when switching away from and back to Graph View.
