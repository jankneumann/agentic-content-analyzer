# Change: Fix Theme Analysis

## Why

The Theme Analysis feature is non-functional due to three issues:

1. **Critical bug**: The Alembic migration `59fbc6999804_add_theme_analysis_table.py` is a no-op (`pass` in both upgrade/downgrade). The `theme_analyses` table was never created in the database. Every analysis attempt fails silently when the API tries to INSERT, and the frontend polls forever, showing "No theme analysis yet."

2. **Stub buttons**: The "Table View" and "Graph View" buttons in `web/src/routes/themes.tsx:162-169` have no `onClick` handlers. TypeScript types (`GraphData`, `GraphNode`, `GraphLink`) and React Query keys (`graph`, `entities`, `relationships`) are pre-defined but unused.

3. **Missing visualization components**: No table or graph visualization components exist. The current display is card-based only (top 10 themes with scores).

The backend is fully implemented: API routes, ThemeAnalyzer processor, Graphiti/Neo4j integration, historical context enrichment, and LLM provider failover all work. Neo4j is started by `make dev-bg`. The issue is purely persistence (migration) and presentation (frontend).

## What Changes

### 1. Fix the empty Alembic migration

Replace the no-op migration body with actual `CREATE TABLE theme_analyses` DDL matching the `ThemeAnalysis` ORM model in `src/models/theme.py`. This includes:
- PG enum type `analysisstatus` (queued/running/completed/failed)
- All columns: id, status, analysis_date, start_date, end_date, content_count, content_ids (JSON), themes (JSON), total_themes, emerging_themes_count, top_theme, agent_framework, model_used, model_version, processing_time_seconds, token_usage, cross_theme_insights (JSON), error_message, created_at
- Indexes: status, analysis_date, created_at, composite (status, created_at)

### 2. Implement Table View component

A sortable, filterable table showing all themes from an analysis:
- Columns: Name, Category, Trend, Relevance Score, Strategic/Tactical scores, Mention Count, Key Points
- Sorting by any column
- Category and trend filter chips
- Click-to-expand for full theme details including historical context

### 3. Implement Graph View with two visualizations

**3a. Force-directed network graph** (theme relationships):
- Themes as nodes (sized by relevance, colored by category)
- Edges from `related_themes` field
- Interactive: hover for details, click to select, zoom/pan
- Library: `react-force-graph-2d` (lightweight, WebGL-backed)

**3b. Timeline/evolution chart** (theme trends over time):
- X-axis: time, Y-axis: themes
- Visual encoding of trend (emerging/growing/established/declining)
- Shows first_seen → last_seen span per theme
- Library: `recharts` (composable React chart components)

### 4. Wire up the buttons

- Table View toggles a `view` state to `"table"` and renders `ThemeTableView`
- Graph View toggles to `"graph"` and renders a tabbed `ThemeGraphView` (Network | Timeline)
- Default remains the existing card view (`"cards"`)
- Active button gets a visual indicator

## Approaches Considered

### Approach 1: Fix migration + Full visualization suite (Recommended)

Fix the migration and implement both Table View and Graph View with two sub-visualizations (network + timeline). Install `react-force-graph-2d` and `recharts` as new dependencies.

**Pros:**
- Delivers the complete theme analysis experience
- Both libraries are lightweight and well-maintained
- Graph types defined in TypeScript are immediately useful
- Network graph naturally represents the `related_themes` data
- Timeline chart shows temporal evolution that's already computed by the backend

**Cons:**
- Two new npm dependencies
- Graph View requires building a data transformation layer (analysis result → GraphData)
- More testing surface area

**Effort:** M

### Approach 2: Fix migration + Table View only, defer Graph View

Fix the migration and implement only the Table View. Graph View button shows a "Coming Soon" placeholder.

**Pros:**
- Smaller scope, faster delivery
- Table view is simpler to implement and test
- No new visualization dependencies

**Cons:**
- Graph View remains non-functional
- Pre-defined graph types and query keys stay unused
- Misses the most visually compelling part of the feature

**Effort:** S

### Approach 3: Fix migration only, defer all UI

Just fix the migration. Theme analysis runs and results display in the existing card layout.

**Pros:**
- Minimal change, lowest risk
- Unblocks the core analysis pipeline immediately

**Cons:**
- Both buttons remain dead
- No tabular or graph exploration of themes
- Doesn't address the user-facing UX gap

**Effort:** XS

### Selected Approach

**Approach 1: Fix migration + Full visualization suite** — selected by user. Delivers the complete experience with both network graph and timeline visualization. The two new dependencies (`react-force-graph-2d`, `recharts`) are standard, well-maintained libraries.

## Scope

### In scope
- Fix Alembic migration for `theme_analyses` table
- ThemeTableView component with sorting/filtering
- ThemeGraphView component with Network and Timeline tabs
- Button wiring with view state toggle
- Frontend unit tests for new components
- E2E test for theme analysis workflow

### Out of scope
- Backend changes (already fully implemented)
- New API endpoints for graph data (client-side transformation of existing data)
- Neo4j direct query endpoints for entities/relationships (future enhancement)
- Real-time theme streaming
