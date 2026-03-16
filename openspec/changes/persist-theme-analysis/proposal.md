## Why

Theme analysis results are stored in ephemeral Python dicts and lost on every API restart. This prevents tracking how themes evolve over time — the core value proposition of the knowledge graph integration. Users cannot compare analyses across weeks to identify emerging or disappearing topics, and past analysis results are permanently lost.

## What Changes

- **Create `theme_analyses` PostgreSQL table** via Alembic migration (ORM model exists at `src/models/theme.py:35-64` but was never migrated; original migration `59fbc6999804` is a no-op)
- **Extend `ThemeAnalysis` ORM model** with `status` (queued/running/completed/failed), `cross_theme_insights`, `error_message`, and `created_at` columns
- **Rename legacy fields**: `newsletter_count` → `content_count`, `newsletter_ids` → `content_ids` throughout models, routes, and frontend (**BREAKING** — direct rename, no backward compatibility)
- **Replace in-memory storage** in `theme_routes.py` with DB persistence following the `digest_routes.py` background task pattern
- **Write analysis results to Neo4j** via Graphiti `add_episode()` — each completed analysis becomes a timestamped episode so future analyses can query past theme data for temporal evolution
- **Fix broken Alembic merge migrations** (`85939732a918` and `a23a53ea737b` reference non-existent revisions)
- **Add analysis history UI** to the frontend themes page with date ranges, theme counts, and status badges
- **Update tests** for DB-backed theme routes

## Capabilities

### New Capabilities
- `theme-analysis`: Persistent theme analysis with temporal evolution tracking, PostgreSQL storage, Neo4j episode writeback, and analysis history browsing

### Modified Capabilities
- `pipeline`: Theme analysis step now persists results to database and knowledge graph
- `frontend-tables`: Themes page gains analysis history list with past analysis browsing

## Impact

- **Backend**: `src/models/theme.py`, `src/api/theme_routes.py`, `src/processors/theme_analyzer.py`, `src/storage/graphiti_client.py`
- **Database**: New `theme_analyses` table + `analysisstatus` PG enum; broken merge migrations fixed
- **Frontend**: `web/src/routes/themes.tsx`, `web/src/lib/api/themes.ts`, `web/src/hooks/use-themes.ts`, `web/src/types/theme.ts`
- **Tests**: `tests/api/test_theme_api.py`, `tests/api/conftest.py` (add DB patch target)
- **API**: `GET /themes` gains `offset` parameter; response field names change from `newsletter_*` to `content_*`
