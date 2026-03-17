## 1. Fix Alembic Migration Chain

- [x] 1.1 Delete broken merge migration `alembic/versions/85939732a918_merge_multiple_heads.py` (references non-existent `a1b2c3d4e5f6`)
- [x] 1.2 Delete broken merge migration `alembic/versions/a23a53ea737b_merge_heads.py` (references non-existent `b1b2c3d4e5f6`)
- [x] 1.3 Create clean single-head merge migration via `alembic merge heads`
- [x] 1.4 Verify single head with `python scripts/check_alembic_heads.py`

## 2. Extend ThemeAnalysis ORM Model

- [x] 2.1 Add `AnalysisStatus` enum (`queued`, `running`, `completed`, `failed`) to `src/models/theme.py`
- [x] 2.2 Add `status` column (SQLEnum, indexed, default QUEUED) to `ThemeAnalysis`
- [x] 2.3 Add `cross_theme_insights` (JSON, nullable), `error_message` (Text, nullable), `created_at` (DateTime, indexed) columns
- [x] 2.4 Rename `newsletter_count` → `content_count` and `newsletter_ids` → `content_ids` in the ORM model
- [x] 2.5 Rename `newsletter_count` → `content_count` and `newsletter_ids` → `content_ids` in the `ThemeAnalysisResult` Pydantic model
- [x] 2.6 Rename `newsletter_ids` → `content_ids` in the `ThemeData` Pydantic model
- [x] 2.7 Add `id: int | None = None` field to `ThemeAnalysisResult` Pydantic model
- [x] 2.8 Fix deprecated `datetime.utcnow` → `datetime.now(UTC)` in ORM defaults and Pydantic defaults

## 3. Create Alembic Migration

- [x] 3.1 Create migration for `theme_analyses` table with all columns (original + new from step 2)
- [x] 3.2 Create `analysisstatus` PG enum in migration with `checkfirst=True`
- [x] 3.3 Add indexes on `analysis_date`, `status`, `created_at`
- [x] 3.4 Make migration idempotent (check `information_schema.tables` before create)
- [x] 3.5 Run `alembic upgrade head` and verify table exists with correct schema

## 4. Refactor Theme Routes — DB Persistence

- [x] 4.1 Remove in-memory dicts (`_analysis_results`, `_analysis_counter`, `_analysis_status`) from `src/api/theme_routes.py`
- [x] 4.2 Add DB imports (`get_db`, `ThemeAnalysis`, `AnalysisStatus`)
- [x] 4.3 Rewrite `POST /analyze` to create `ThemeAnalysis` DB record with `status=QUEUED`, return DB-generated ID
- [x] 4.4 Rewrite `run_theme_analysis()` background task: update status to RUNNING, persist result on success (serialize themes with `model_dump(mode="json")`), set FAILED with error_message on failure
- [x] 4.5 Rewrite `GET /analysis/{id}` to query DB by ID
- [x] 4.6 Rewrite `GET /latest` to query DB for most recent completed analysis
- [x] 4.7 Rewrite `GET /themes` (list) to query DB with `offset`/`limit` pagination, ordered by `created_at` desc
- [x] 4.8 Add `_orm_to_response()` helper to convert ORM record to API response dict with `content_count`/`content_ids` field names

## 5. Update Theme Analyzer — Rename Fields

- [x] 5.1 Update `src/processors/theme_analyzer.py` to use `content_count`/`content_ids` when building `ThemeAnalysisResult`
- [x] 5.2 Update `src/processors/historical_context.py` if it references `newsletter_ids`

## 6. Neo4j Episode Writeback

- [x] 6.1 Add `add_theme_analysis_episode()` method to `src/storage/graphiti_client.py` that formats a completed `ThemeAnalysisResult` as a structured markdown episode and calls `self.graphiti.add_episode()`
- [x] 6.2 Call `add_theme_analysis_episode()` from `run_theme_analysis()` in theme_routes after successful DB persistence
- [x] 6.3 Make Neo4j writeback fail-safe (log errors but don't fail the analysis if Neo4j is unavailable)

## 7. Frontend — API Client & Hooks

- [x] 7.1 Add `start_date`, `end_date` fields to `AnalysisListItem` interface in `web/src/lib/api/themes.ts`
- [x] 7.2 Add `offset` parameter to `listAnalyses()` function
- [x] 7.3 Update `ThemeAnalysisResult` type to use `content_count`/`content_ids` in `web/src/types/theme.ts`
- [x] 7.4 Add `useAnalysisById(id)` hook to `web/src/hooks/use-themes.ts`

## 8. Frontend — Themes Page History

- [x] 8.1 Add `useAnalysesList(20)` call and history state to `web/src/routes/themes.tsx`
- [x] 8.2 Add "Analysis History" card section showing past analyses with date range, theme count, time ago, and status badges
- [x] 8.3 Add click handler to load a past analysis into the main display card
- [x] 8.4 Show history section only when more than one analysis exists

## 9. Update Tests

- [x] 9.1 Add `"src.api.theme_routes.get_db"` to `db_patch_targets` in `tests/api/conftest.py`
- [x] 9.2 Update existing tests in `tests/api/test_theme_api.py` for DB-backed behavior (POST creates DB record, list returns DB records)
- [x] 9.3 Add test: `test_analysis_creates_db_record` — verify POST creates ThemeAnalysis with QUEUED status
- [x] 9.4 Add test: `test_latest_returns_most_recent_completed` — insert multiple records, verify latest completed returned
- [x] 9.5 Add test: `test_response_uses_content_field_names` — verify `content_count`/`content_ids` in response
- [x] 9.6 Add test: `test_list_supports_offset` — pagination works correctly
- [x] 9.7 Update E2E mock data in `web/tests/e2e/fixtures/mock-data.ts` for analysis history
- [x] 9.8 Run `pytest tests/api/test_theme_api.py -v` and verify all tests pass
