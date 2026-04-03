# Design: Fix Theme Analysis

## D1. Migration Strategy

The original migration `59fbc6999804` is a no-op but is already in the Alembic chain (referenced by `d75166ebc782`). It cannot be edited.

**Decision**: Create a new migration at the current head (`f9a8b7c6d5e5`) that creates the `theme_analyses` table and `analysisstatus` enum. The migration must be idempotent-safe (check `IF NOT EXISTS` for enum type creation since PG enums can't be created twice).

**Schema**: Mirrors `ThemeAnalysis` ORM model in `src/models/theme.py`:
- PG enum `analysisstatus` with values: queued, running, completed, failed
- Table `theme_analyses` with all columns from the ORM model
- Indexes: `ix_theme_analyses_status`, `ix_theme_analyses_analysis_date`, `ix_theme_analyses_created_at`, composite `ix_theme_analyses_status_created`

## D2. Frontend View Architecture

**View state pattern**: The themes page uses a `view` state variable (`"cards" | "table" | "graph"`) to toggle between three display modes. Active button gets `variant="default"` styling.

```
ThemesPage
  ├── [view="cards"]  → Existing card layout (default, unchanged)
  ├── [view="table"]  → ThemeTableView component (new)
  └── [view="graph"]  → ThemeGraphView component (new)
                          ├── [tab="network"]  → ForceGraph2D
                          └── [tab="timeline"] → Recharts timeline
```

All three views consume the same `displayAnalysis` data — no new API calls needed.

## D3. Table View Design

**Component**: `web/src/components/themes/ThemeTableView.tsx`

Uses the existing shadcn `Table` and `SortableTableHead` components. No new UI dependencies.

| Column | Source | Sortable |
|--------|--------|----------|
| Name | `theme.name` | Yes |
| Category | `theme.category` | Yes (alphabetical) |
| Trend | `theme.trend` | Yes (enum order) |
| Relevance | `theme.relevance_score` | Yes (default desc) |
| Strategic | `theme.strategic_relevance` | Yes |
| Tactical | `theme.tactical_relevance` | Yes |
| Mentions | `theme.mention_count` | Yes |
| Key Points | `theme.key_points[0..1]` | No |

**Filtering**: Category filter chips above the table. Trend filter as badge-style toggles.

**Expand**: Click a row to expand an accordion showing: full description, all key points, historical context, related themes.

## D4. Network Graph Design

**Component**: `web/src/components/themes/ThemeNetworkGraph.tsx`

**Library**: `react-force-graph-2d` — lightweight 2D force-directed graph using Canvas/WebGL.

**Data transformation** (client-side, from `ThemeAnalysisResult`):
- Each theme → `GraphNode` with `type="theme"`, sized by `relevance_score`, colored by `category`
- Each entry in `theme.related_themes` → `GraphLink` connecting theme nodes
- Entity nodes from `theme.historical_context.recent_mentions` (optional, toggleable)

**Interactions**:
- Hover: tooltip with theme name, category, trend, relevance score
- Click: select theme, highlight connected nodes
- Zoom/pan: built-in canvas controls
- Legend: color-coded by category

**Color palette** (by category):
- ml_ai: blue, devops_infra: green, data_engineering: orange, business_strategy: purple, tools_products: teal, research_academia: red, security: yellow, other: gray

## D5. Timeline Chart Design

**Component**: `web/src/components/themes/ThemeTimelineChart.tsx`

**Library**: `recharts` — composable React chart components.

**Chart type**: Horizontal bar/range chart:
- Y-axis: theme names (sorted by first_seen)
- X-axis: date range
- Each bar spans `first_seen` → `last_seen`
- Bar color: category-based (same palette as network graph)
- Bar opacity: relevance_score (higher = more opaque)
- Badge on bar: trend icon (arrow-up for emerging/growing, dash for established, arrow-down for declining)

**Alternative considered**: Line chart with mention_count over time. Rejected because we don't have per-day mention data — only aggregate `first_seen`/`last_seen`/`mention_count` per theme.

## D6. New Dependencies

| Package | Version | Size | Purpose |
|---------|---------|------|---------|
| `react-force-graph-2d` | ^1.25 | ~45KB gzipped | Force-directed graph |
| `recharts` | ^2.12 | ~140KB gzipped | Timeline chart |

Both are well-maintained, widely used, and have TypeScript types included.
