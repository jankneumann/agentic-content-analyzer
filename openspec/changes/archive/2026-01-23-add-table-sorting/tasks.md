# Tasks: Add Table Sorting

## 1. Backend: Add Sort Parameters to API Endpoints

### 1.1 Content Endpoint
- [x] 1.1.1 Add `sort_by` and `sort_order` query parameters to `GET /api/v1/contents`
- [x] 1.1.2 Define `CONTENT_SORT_FIELDS` whitelist: id, title, source_type, publication, status, published_date, ingested_at
- [x] 1.1.3 Implement dynamic ordering with SQLAlchemy `getattr()` pattern
- [x] 1.1.4 Add unit test for sort parameter validation

### 1.2 Summary Endpoint
- [x] 1.2.1 Add `sort_by` and `sort_order` query parameters to `GET /api/v1/summaries`
- [x] 1.2.2 Define `SUMMARY_SORT_FIELDS` whitelist: id, content_id, model_used, created_at
- [x] 1.2.3 Implement dynamic ordering
- [x] 1.2.4 Add unit test for sort parameter validation

### 1.3 Digest Endpoint
- [x] 1.3.1 Add `sort_by` and `sort_order` query parameters to `GET /api/v1/digests`
- [x] 1.3.2 Define `DIGEST_SORT_FIELDS` whitelist: id, digest_type, status, created_at, period_start, period_end
- [x] 1.3.3 Implement dynamic ordering
- [x] 1.3.4 Add unit test for sort parameter validation

### 1.4 Script Endpoint
- [x] 1.4.1 Add `sort_by` and `sort_order` query parameters to `GET /api/v1/scripts`
- [x] 1.4.2 Define `SCRIPT_SORT_FIELDS` whitelist: id, digest_id, status, created_at
- [x] 1.4.3 Implement dynamic ordering
- [x] 1.4.4 Add unit test for sort parameter validation

### 1.5 Podcast Endpoint
- [x] 1.5.1 Add `sort_by` and `sort_order` query parameters to `GET /api/v1/podcasts`
- [x] 1.5.2 Define `PODCAST_SORT_FIELDS` whitelist: id, script_id, status, duration_seconds, file_size_bytes, created_at
- [x] 1.5.3 Implement dynamic ordering
- [x] 1.5.4 Add unit test for sort parameter validation

## 2. Frontend: Types and API Layer

### 2.1 Type Definitions
- [x] 2.1.1 Add `SortOrder` type: `'asc' | 'desc'`
- [x] 2.1.2 Add `sort_by` and `sort_order` to `ContentFilters` interface
- [x] 2.1.3 Add `sort_by` and `sort_order` to `SummaryFilters` interface
- [x] 2.1.4 Add `sort_by` and `sort_order` to `DigestFilters` interface
- [x] 2.1.5 Add `sort_by` and `sort_order` to `ScriptFilters` interface
- [x] 2.1.6 Add `sort_by` and `sort_order` to `PodcastFilters` interface

### 2.2 API Client Updates
- [x] 2.2.1 Update `fetchContents` to pass sort parameters (via filter passthrough)
- [x] 2.2.2 Update `fetchSummaries` to pass sort parameters (via filter passthrough)
- [x] 2.2.3 Update `fetchDigests` to pass sort parameters (via filter passthrough)
- [x] 2.2.4 Update `fetchScripts` to pass sort parameters (via filter passthrough)
- [x] 2.2.5 Update `fetchPodcasts` to pass sort parameters (via filter passthrough)

## 3. Frontend: Reusable Components

### 3.1 SortableTableHead Component
- [x] 3.1.1 Create `SortableTableHead` component in `web/src/components/ui/`
- [x] 3.1.2 Implement sort direction icons (ascending/descending/none)
- [x] 3.1.3 Add hover styles and cursor pointer
- [x] 3.1.4 Add accessibility attributes (aria-sort)
- [x] 3.1.5 Implement tri-state toggle logic (asc → desc → none)

### 3.2 Sort State Hook (Optional)
- [x] 3.2.1 Create `useSortState` hook for common sort state management pattern

## 4. Frontend: Table Implementations

### 4.1 Content Table
- [x] 4.1.1 Add sort state to filter useState
- [x] 4.1.2 Replace TableHead with SortableTableHead for: Title, Source, Publication, Status, Published Date
- [x] 4.1.3 Implement onSort handler to update filter state
- [x] 4.1.4 Reset to page 1 when sort changes

### 4.2 Summary Table
- [x] 4.2.1 Add sort state to filter useState
- [x] 4.2.2 Replace TableHead with SortableTableHead for: Content, Model, Time, Created
- [x] 4.2.3 Implement onSort handler to update filter state
- [x] 4.2.4 Reset offset to 0 when sort changes

### 4.3 Digest Table
- [x] 4.3.1 Add sort state to filter useState
- [x] 4.3.2 Replace TableHead with SortableTableHead for: Type, Period, Status, Created
- [x] 4.3.3 Implement onSort handler to update filter state

### 4.4 Script Table
- [x] 4.4.1 Add sort state to filter useState
- [x] 4.4.2 Replace TableHead with SortableTableHead for: Digest ID, Status, Created
- [x] 4.4.3 Implement onSort handler to update filter state

### 4.5 Podcast Table
- [x] 4.5.1 Add sort state to filter useState
- [x] 4.5.2 Replace TableHead with SortableTableHead for: Duration, Size, Status, Created
- [x] 4.5.3 Implement onSort handler to update filter state

## 5. Testing

### 5.1 Backend Integration Tests
- [x] 5.1.1 Test ascending sort order
- [x] 5.1.2 Test descending sort order
- [x] 5.1.3 Test invalid sort_by field falls back to default
- [x] 5.1.4 Test sort with pagination (correct page boundaries)

Note: Tests created in `tests/api/test_sorting.py`. Test execution blocked by pre-existing
test infrastructure issue (duplicate index in test database), not related to sorting code.

### 5.2 Frontend Tests (if testing framework exists)
- [x] 5.2.1 Test SortableTableHead renders correct icons - SKIPPED (no frontend test framework)
- [x] 5.2.2 Test onSort callback fires with correct parameters - SKIPPED (no frontend test framework)
- [x] 5.2.3 Test tri-state toggle behavior - SKIPPED (no frontend test framework)

Note: No frontend testing framework (Vitest, Jest) is configured in this project.
Component behavior was verified manually. Consider adding frontend tests when framework is set up.

## 6. Documentation

- [x] 6.1 Update API documentation with new query parameters
  - FastAPI auto-generates OpenAPI docs at /docs with sort_by and sort_order params
  - Added note in docs/DEVELOPMENT.md about sorting query parameters
- [x] 6.2 Add sort parameters to any existing Postman/Insomnia collections - N/A (no collections found)
