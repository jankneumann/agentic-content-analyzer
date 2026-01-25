# Design: Table Sorting Implementation

## Context

The application has 5 data tables (Content, Summary, Digest, Script, Podcast) that display lists with various columns. Currently, all tables have hardcoded sort order (`created_at DESC` or similar). Users need the ability to sort by any visible column to efficiently navigate and analyze data.

**Stakeholders**: End users reviewing digests, developers debugging pipelines, admins monitoring content flow.

**Constraints**:
- Must work with existing pagination (page/page_size for Content, offset/limit for others)
- Backend sorting required for correct paginated results
- Must maintain type safety (TypeScript frontend, mypy backend)

## Goals / Non-Goals

### Goals
- Enable sorting by all user-visible columns in each table
- Provide visual feedback for current sort state (column + direction)
- Maintain consistent UX across all 5 tables
- Preserve default sort order when no explicit sort requested
- Type-safe implementation (frontend + backend)

### Non-Goals
- Multi-column sorting (sort by A, then B) - future enhancement
- Client-side sorting for small datasets - always use server
- Sorting by computed fields not in database
- Remembering sort preferences across sessions (localStorage)

## Decisions

### Decision 1: Server-Side Sorting Only

**What**: All sorting happens in the database, never in frontend JavaScript.

**Why**:
- Pagination requires sorted data before LIMIT/OFFSET
- Consistent results regardless of page size
- Leverages database indexes for performance
- Avoids loading entire dataset to client

**Alternative considered**: Client-side sorting for unpaginated tables (Digest, Script, Podcast)
- Rejected: Inconsistent UX, won't scale if pagination added later

### Decision 2: Reusable SortableTableHead Component

**What**: Create a single component for sortable column headers.

```tsx
interface SortableTableHeadProps {
  column: string;           // API field name
  label: string;            // Display text
  currentSort?: string;     // Currently sorted column
  currentOrder?: 'asc' | 'desc';
  onSort: (column: string, order: 'asc' | 'desc') => void;
}
```

**Why**:
- DRY: 5 tables × ~6 columns = ~30 column headers
- Consistent visual treatment (hover state, icons)
- Centralized accessibility attributes

### Decision 3: Sort State in Existing Filter Objects

**What**: Add `sort_by` and `sort_order` to existing filter types.

```typescript
interface ContentFilters {
  // ... existing filters
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}
```

**Why**:
- Filters already passed to hooks and API
- React Query cache keys include filters (automatic cache invalidation)
- No new state management required

### Decision 4: Backend Field Whitelisting

**What**: Each endpoint defines allowed sort fields, rejects invalid values.

```python
CONTENT_SORT_FIELDS = {"id", "title", "source_type", "publication", "status", "published_date", "ingested_at"}

if sort_by not in CONTENT_SORT_FIELDS:
    sort_by = "ingested_at"  # Fallback to default
```

**Why**:
- Prevents arbitrary column access (security)
- Clear documentation of sortable columns
- Graceful degradation for invalid input

**Alternative considered**: Raise 400 error for invalid sort_by
- Rejected: Better UX to use default than to fail

### Decision 5: Tri-State Sort Toggle

**What**: Clicking a column cycles: ascending → descending → default (no sort)

**Why**:
- Standard UX pattern (Excel, Google Sheets)
- Allows user to return to default order
- Clear visual states for each mode

## Risks / Trade-offs

### Risk 1: Performance on Large Tables
- **Risk**: Sorting by non-indexed column could be slow
- **Mitigation**: All sortable columns are either indexed or have reasonable cardinality
- **Monitoring**: Add query timing logs if needed

### Risk 2: Inconsistent Sort Behavior Across Tables
- **Risk**: Different tables have different default sorts
- **Mitigation**: Document defaults in UI (tooltip on header), maintain existing defaults

### Risk 3: Type Safety Across Stack
- **Risk**: Frontend column names might not match backend
- **Mitigation**: Define shared constants or validate at integration test level

## Migration Plan

No migration needed - this is an additive feature:

1. **Phase 1: Backend** (can deploy independently)
   - Add `sort_by` and `sort_order` parameters
   - Existing behavior unchanged when parameters omitted

2. **Phase 2: Frontend** (deploy after backend)
   - Add SortableTableHead component
   - Update each table one at a time
   - Each table can be updated independently

**Rollback**: Remove frontend changes; backend continues to work with defaults.

## Open Questions

1. ~~Should we persist sort preferences in localStorage?~~ Decided: No, not in initial scope
2. ~~Should clicking sorted column toggle direction or reset?~~ Decided: Toggle direction, third click resets
3. Should we add sort parameters to URL query string for shareable links? (Nice to have, not required for MVP)
