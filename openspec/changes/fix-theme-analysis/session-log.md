---

## Phase: Plan (2026-04-02)

**Agent**: Claude Opus 4.6 | **Session**: plan-feature

### Decisions
1. **New migration at head, not edit of no-op** — The original migration `59fbc6999804` is already in the Alembic chain (referenced by `d75166ebc782`). Cannot be edited. New migration at current head `f9a8b7c6d5e5` creates the table.
2. **Client-side graph data transformation** — No new backend API endpoints for graph data. Transform existing `ThemeAnalysisResult` data into `GraphData` format in the frontend. The `related_themes` field already provides edge data.
3. **Two visualization libraries** — `react-force-graph-2d` for network graph (lightweight Canvas/WebGL), `recharts` for timeline chart (composable React charts). No existing chart libraries in the project.
4. **Coordinated tier** — Coordinator available with full capabilities. 5 work packages with clear scope boundaries.

### Alternatives Considered
- Editing the original no-op migration: rejected because it's already in the chain (downstream `d75166ebc782` references it)
- Server-side graph data endpoint: rejected because all data is already in the analysis response
- D3 for all visualizations: rejected in favor of higher-level React-specific libraries

### Trade-offs
- Accepted two new dependencies over building custom visualizations because maintenance cost is lower and delivery is faster
- Accepted horizontal bar chart over line chart for timeline because we lack per-day granularity (only have first_seen/last_seen per theme)

### Open Questions
- [ ] Verify react-force-graph-2d works with the project's React version
- [ ] Check if recharts has SSR compatibility issues (unlikely with Vite SPA)

### Context
User reported theme analysis completely non-functional: buttons do nothing, analysis returns no themes. Root cause is an empty Alembic migration that never created the `theme_analyses` table. Plan covers the migration fix plus full Table View and Graph View implementations.
