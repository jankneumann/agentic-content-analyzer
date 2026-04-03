# Tasks: Fix Theme Analysis

## Phase 1: Database Fix (Backend)

- [ ] 1.1 Write migration test — verify `theme_analyses` table can be created and rolled back
  **Spec scenarios**: theme-analysis.1
  **Design decisions**: D1 (new migration at head, not editing the no-op)
  **Dependencies**: None

- [ ] 1.2 Create Alembic migration `create_theme_analyses_table` at current head (`f9a8b7c6d5e5`)
  - Create `analysisstatus` enum type (`IF NOT EXISTS` for idempotency)
  - Create `theme_analyses` table with all columns from `ThemeAnalysis` ORM model
  - Create indexes: status, analysis_date, created_at, composite (status, created_at)
  - Downgrade: drop table, drop enum
  **Spec scenarios**: theme-analysis.1
  **Design decisions**: D1
  **Dependencies**: 1.1

- [ ] 1.3 Verify end-to-end: run `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head` again
  **Spec scenarios**: theme-analysis.1
  **Dependencies**: 1.2

## Phase 2: Frontend Dependencies

- [ ] 2.1 Install `react-force-graph-2d` and `recharts` in `web/`
  **Design decisions**: D6
  **Dependencies**: None

## Phase 3: Table View (Frontend)

- [ ] 3.1 Write tests for ThemeTableView — renders themes, sorting works, filtering works, expand/collapse works
  **Spec scenarios**: theme-analysis.2
  **Design decisions**: D3
  **Dependencies**: None

- [ ] 3.2 Create `web/src/components/themes/ThemeTableView.tsx`
  - Sortable columns using existing `SortableTableHead` component
  - Category filter chips and trend badge toggles
  - Expandable rows with full details
  - Empty state for zero themes
  **Spec scenarios**: theme-analysis.2
  **Design decisions**: D3
  **Dependencies**: 3.1

## Phase 4: Graph View (Frontend)

- [ ] 4.1 Write tests for ThemeNetworkGraph — renders nodes/edges, data transformation correct
  **Spec scenarios**: theme-analysis.3
  **Design decisions**: D4
  **Dependencies**: 2.1

- [ ] 4.2 Create `web/src/components/themes/ThemeNetworkGraph.tsx`
  - Transform ThemeAnalysisResult into GraphData (nodes from themes, edges from related_themes)
  - Force-directed layout with react-force-graph-2d
  - Category-based coloring, relevance-based sizing
  - Hover tooltip, click selection
  - Empty state
  **Spec scenarios**: theme-analysis.3
  **Design decisions**: D4
  **Dependencies**: 4.1

- [ ] 4.3 Write tests for ThemeTimelineChart — renders bars, correct date spans, category colors
  **Spec scenarios**: theme-analysis.4
  **Design decisions**: D5
  **Dependencies**: 2.1

- [ ] 4.4 Create `web/src/components/themes/ThemeTimelineChart.tsx`
  - Horizontal bar chart with recharts
  - Bars span first_seen → last_seen per theme
  - Category-based coloring, relevance-based opacity
  - Trend indicators
  - Sorted by first_seen
  - Empty state
  **Spec scenarios**: theme-analysis.4
  **Design decisions**: D5
  **Dependencies**: 4.3

- [ ] 4.5 Create `web/src/components/themes/ThemeGraphView.tsx` — tabbed container with Network and Timeline
  **Spec scenarios**: theme-analysis.6
  **Design decisions**: D2
  **Dependencies**: 4.2, 4.4

## Phase 5: View Toggle & Integration (Frontend)

- [ ] 5.1 Write tests for view toggle — button state, correct component rendered per view
  **Spec scenarios**: theme-analysis.5
  **Dependencies**: None

- [ ] 5.2 Update `web/src/routes/themes.tsx` — wire Table View and Graph View buttons
  - Add `view` state: `"cards" | "table" | "graph"`
  - Add `graphTab` state: `"network" | "timeline"` (preserved across view switches)
  - Wire onClick handlers on Table View and Graph View buttons
  - Conditionally render ThemeTableView, ThemeGraphView, or existing card layout
  - Active button styling
  **Spec scenarios**: theme-analysis.5, theme-analysis.6
  **Design decisions**: D2
  **Dependencies**: 3.2, 4.5, 5.1

- [ ] 5.3 Export new components from `web/src/components/themes/index.ts`
  **Dependencies**: 3.2, 4.5

## Phase 6: E2E & Smoke Test

- [ ] 6.1 Add E2E test — trigger analysis, verify table view renders themes, verify graph view renders
  **Spec scenarios**: theme-analysis.2, theme-analysis.3, theme-analysis.4, theme-analysis.5
  **Dependencies**: 5.2
