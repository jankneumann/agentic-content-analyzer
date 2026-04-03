# Spec: Theme Analysis (Delta)

## ADDED Requirements

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
