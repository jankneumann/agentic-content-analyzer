# Change: Add Column Sorting to Data Tables

## Why

Users currently cannot sort table data by column headers in the Content, Summary, Digest, Script, and Podcast tables. This makes it difficult to find specific items, identify patterns, or review data in a meaningful order. Sorting is a fundamental UX expectation for data tables.

## What Changes

### Frontend (5 tables)
- Add clickable column headers with sort indicators (ascending/descending arrows)
- Implement sort state management in filter objects
- Update API calls to pass `sort_by` and `sort_order` parameters
- Create reusable `SortableTableHead` component for consistency

### Backend (5 endpoints)
- Add `sort_by` and `sort_order` query parameters to list endpoints
- Implement dynamic ordering with SQLAlchemy
- Add field whitelisting to prevent SQL injection
- Maintain backward compatibility (default sort order preserved)

### Tables and Their Sortable Columns
| Table | Sortable Columns |
|-------|------------------|
| Content | Title, Source, Publication, Status, Published Date, Ingested Date |
| Summary | Title, Publication, Model Used, Created Date |
| Digest | Type, Period, Status, Created Date |
| Script | Digest ID, Status, Created Date |
| Podcast | Script ID, Duration, File Size, Status, Created Date |

## Impact

- **Affected specs**: New spec `frontend-tables` (no existing spec covers table UI)
- **Affected code**:
  - Backend: `src/api/routes/content_routes.py`, `summary_routes.py`, `digest_routes.py`, `script_routes.py`, `podcast_routes.py`
  - Frontend: `web/src/routes/contents.tsx`, `summaries.tsx`, `digests.tsx`, `scripts.tsx`, `podcasts.tsx`
  - Frontend: `web/src/hooks/use-*.ts` (filter type updates)
  - Frontend: `web/src/types/` (filter interface updates)
  - Frontend: `web/src/components/ui/` (new SortableTableHead component)
- **No breaking changes**: Default sort behavior unchanged, parameters are optional
- **No database changes**: Uses existing indexed columns
