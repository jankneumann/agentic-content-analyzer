# Design: Content Query Builder

## Decision 1: ContentQuery Model Location

**Choice**: New file `src/models/query.py`

Placing the shared query model in `src/models/` alongside `content.py`, `summary.py`, and `digest.py` follows the existing convention. It imports `ContentSource` and `ContentStatus` from `content.py`.

```python
# src/models/query.py
from pydantic import BaseModel, Field
from datetime import datetime
from src.models.content import ContentSource, ContentStatus

# Validated against this allowlist — matches content_routes.py CONTENT_SORT_FIELDS
CONTENT_SORT_FIELDS = {"id", "title", "source_type", "publication", "status", "published_date", "ingested_at"}

PREVIEW_SAMPLE_LIMIT = 10  # Max sample titles in preview


class ContentQuery(BaseModel):
    """Reusable content selection criteria for batch operations.

    Null field semantics: None means "no filter" (match all).
    Empty list [] is treated the same as None.
    """
    source_types: list[ContentSource] | None = None
    statuses: list[ContentStatus] | None = None
    publications: list[str] | None = None
    publication_search: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    search: str | None = None
    limit: int | None = Field(default=None, gt=0)
    sort_by: str = Field(default="published_date")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        if v not in CONTENT_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by '{v}'. Valid fields: {sorted(CONTENT_SORT_FIELDS)}")
        return v


class ContentQueryPreview(BaseModel):
    """Preview result showing what a query would match."""
    total_count: int
    by_source: dict[str, int]       # {source_type: count}, alphabetical by key
    by_status: dict[str, int]       # {status: count}, alphabetical by key
    date_range: dict[str, str | None]  # {earliest: ISO str | None, latest: ISO str | None}
    sample_titles: list[str]        # Up to PREVIEW_SAMPLE_LIMIT titles, most recent first
    query: ContentQuery             # Echo back the query for confirmation
```

**Removed from scope**: `tags` (Content model has no tags field — deferred), `exclude_ids` (no CLI/UI exposure needed yet — can be added later without breaking changes).

## Decision 2: Query Execution Service Architecture

**Choice**: New `ContentQueryService` in `src/services/content_query.py`

Follows the existing Client-Service pattern. The service translates `ContentQuery` → SQLAlchemy query, reusing the filter logic currently duplicated in `content_routes.py`.

```python
# src/services/content_query.py
class ContentQueryService:
    def build_query(self, db: Session, query: ContentQuery) -> Query:
        """Build SQLAlchemy query from ContentQuery filters.

        Empty lists are treated as None (no filter).
        """
        q = db.query(Content)

        if query.source_types:
            q = q.filter(Content.source_type.in_(query.source_types))
        if query.statuses:
            q = q.filter(Content.status.in_(query.statuses))
        if query.publications:
            q = q.filter(Content.publication.in_(query.publications))
        if query.publication_search:
            q = q.filter(Content.publication.ilike(f"%{query.publication_search}%"))
        if query.start_date:
            q = q.filter(Content.published_date >= query.start_date)
        if query.end_date:
            q = q.filter(Content.published_date <= query.end_date)
        if query.search:
            q = q.filter(Content.title.ilike(f"%{query.search}%"))

        # Sort_by is already validated by Pydantic
        sort_col = getattr(Content, query.sort_by)
        q = q.order_by(sort_col.desc() if query.sort_order == "desc" else sort_col.asc())

        if query.limit:
            q = q.limit(query.limit)

        return q

    def preview(self, query: ContentQuery) -> ContentQueryPreview:
        """Preview what content matches without loading full records.

        Uses COUNT + GROUP BY for breakdown, separate query for sample titles.
        Returns total_count=0 with empty dicts/lists when no content matches.
        """
        ...

    def resolve(self, query: ContentQuery) -> list[int]:
        """Resolve query to a list of content IDs.

        Returns all matching IDs (no pagination — queries are bounded by limit).
        Callers that need pagination should set query.limit.
        """
        ...
```

### Refactoring content_routes.py

The existing `list_contents` endpoint in `content_routes.py` (lines 310-398) builds its own filter query inline. This will be refactored to use `ContentQueryService.build_query()` internally — same behavior, shared implementation. Regression tests must verify that all existing filter combinations produce identical results before and after refactoring.

**Important**: The existing endpoint uses singular `source_type` (single value), while ContentQuery uses plural `source_types` (list). The endpoint adapter will wrap the single value into a list: `source_types=[source_type] if source_type else None`.

## Decision 3: CLI Flag Design

**Choice**: Typed Typer options that map to ContentQuery fields

```python
# Shared CLI options (src/cli/query_options.py)
source_option = typer.Option(None, "--source", "-s", help="Comma-separated source types (gmail,rss,youtube,...)")
status_option = typer.Option(None, "--status", help="Comma-separated statuses (pending,parsed,completed,...)")
after_option = typer.Option(None, "--after", help="Content published after this date (YYYY-MM-DD)")
before_option = typer.Option(None, "--before", help="Content published before this date (YYYY-MM-DD)")
publication_option = typer.Option(None, "--publication", "-p", help="Filter by publication name")
search_option = typer.Option(None, "--search", "-q", help="Search in title")
dry_run_option = typer.Option(False, "--dry-run", help="Preview matching content without executing")
```

**No conflicts**: `--after`, `--before`, `--search`, `-p/--publication`, `--dry-run` do not conflict with existing flags on `aca summarize pending` (which has `--limit`, `--sync`) or `aca create-digest` (which has `--date`).

**Why comma-separated for multi-value?** Typer doesn't natively support `--source youtube --source rss` repeat syntax cleanly. Comma-separated `--source youtube,rss` is more concise and mirrors the existing `--source` flag in ingestion commands.

### CLI→ContentQuery Translation

```python
def build_query_from_options(
    source: str | None,
    status: str | None,
    after: str | None,
    before: str | None,
    publication: str | None,
    search: str | None,
    limit: int | None = None,
    default_statuses: list[ContentStatus] | None = None,
) -> ContentQuery:
    """Translate CLI options to ContentQuery.

    Validation errors (invalid enum values, bad date format) raise
    typer.BadParameter with descriptive messages listing valid values.
    """
    source_types = None
    if source:
        try:
            source_types = [ContentSource(s.strip()) for s in source.split(",")]
        except ValueError as e:
            valid = ", ".join(s.value for s in ContentSource)
            raise typer.BadParameter(f"Invalid source: {e}. Valid: {valid}")

    statuses = default_statuses
    if status:
        try:
            statuses = [ContentStatus(s.strip()) for s in status.split(",")]
        except ValueError as e:
            valid = ", ".join(s.value for s in ContentStatus)
            raise typer.BadParameter(f"Invalid status: {e}. Valid: {valid}")

    start_date = None
    if after:
        try:
            start_date = datetime.fromisoformat(after)
        except ValueError:
            raise typer.BadParameter(f"Invalid date format '{after}'. Use YYYY-MM-DD.")

    end_date = None
    if before:
        try:
            end_date = datetime.fromisoformat(before)
        except ValueError:
            raise typer.BadParameter(f"Invalid date format '{before}'. Use YYYY-MM-DD.")

    return ContentQuery(
        source_types=source_types,
        statuses=statuses,
        start_date=start_date,
        end_date=end_date,
        publication_search=publication,
        search=search,
        limit=limit,
    )
```

### `--dry-run` behavior

When `--dry-run` is provided, the CLI calls `ContentQueryService.preview()` and displays the `ContentQueryPreview` as a Rich table (or JSON with `--output json`). No batch operation is executed. Both `--dry-run` and `--output json` can be used together: `aca summarize pending --source youtube --dry-run --output json`.

## Decision 4: Extending Summarizer and DigestCreator

**Choice**: Add `ContentQuery` as optional parameter, preserving backward compatibility. Dry-run is handled exclusively at the CLI/API layer — service methods do not take a `dry_run` parameter.

### Summarizer

```python
# Current: summarize_pending_contents(limit=None)
# New:     summarize_pending_contents(limit=None, query=None)

def summarize_pending_contents(self, limit: int | None = None, query: ContentQuery | None = None) -> int:
    with get_db() as db:
        if query:
            # Merge default status constraint if not specified
            if not query.statuses:
                query = query.model_copy(update={"statuses": [ContentStatus.PENDING, ContentStatus.PARSED]})
            svc = ContentQueryService()
            pending_ids = svc.resolve(query)
        else:
            # Original behavior — unchanged
            q = db.query(Content.id).filter(
                Content.status.in_([ContentStatus.PENDING, ContentStatus.PARSED])
            )
            if limit:
                q = q.limit(limit)
            pending_ids = [row[0] for row in q.all()]
    ...
```

**Note**: Uses `model_copy(update=...)` instead of mutating the query — prevents side effects on caller's object.

### DigestCreator

```python
# Current: DigestRequest has period_start, period_end
# New:     DigestRequest gains optional content_query field

class DigestRequest(BaseModel):
    digest_type: DigestType
    period_start: datetime
    period_end: datetime
    content_query: ContentQuery | None = None  # NEW: override content selection
    ...
```

**Merge semantics** for `content_query` with `DigestRequest`:

1. If `content_query` is `None`: original behavior (`status=COMPLETED`, `published_date BETWEEN period_start AND period_end`).
2. If `content_query` is provided:
   - If `content_query.start_date` is `None`: use `period_start` as fallback.
   - If `content_query.end_date` is `None`: use `period_end` as fallback.
   - If `content_query.statuses` is `None` or empty: append `[COMPLETED]` as default (digests require completed content).
   - If `content_query.statuses` includes non-COMPLETED statuses: honor them — user explicitly chose to include e.g. PARSED content in the digest.

**Rationale**: `period_start`/`period_end` are always required on `DigestRequest` (for display and metadata), but `content_query` can override which content is actually fetched. Dates merge as fallbacks, statuses merge as defaults.

## Decision 5: API Endpoint Design

**New endpoint:**

```
POST /api/v1/contents/query/preview
  Body: ContentQuery
  Returns: ContentQueryPreview (HTTP 200)
  Auth: session cookie or X-Admin-Key
  Error: 400 if invalid source_types/statuses/sort_by
  Empty result: 200 with total_count=0, empty breakdowns
```

**Extended endpoints:**

```
POST /api/v1/contents/summarize
  Body: {
    content_ids?: int[],         # Existing field
    query?: ContentQuery,        # NEW: alternative to content_ids
    force?: bool,                # Existing field
    dry_run?: bool               # NEW: return preview without executing
  }
  Precedence: if query provided, it takes precedence over content_ids.
  If neither: default behavior (all PENDING/PARSED).
  If dry_run=true: return ContentQueryPreview (HTTP 200), no jobs enqueued.

POST /api/v1/digests/generate
  Body: {
    ...,                         # Existing fields
    content_query?: ContentQuery, # NEW: override content selection
    dry_run?: bool                # NEW: return preview without generating
  }
  If dry_run=true: return ContentQueryPreview (HTTP 200), no digest created.
```

**Why POST for preview?** The query body can be complex (lists of enums, date ranges). GET with query params would be unwieldy and hit URL length limits.

**Why no separate `/resolve` endpoint?** The resolve operation (returning matched IDs) is an implementation detail used internally by summarize/digest. The preview endpoint gives users what they need: counts, breakdowns, and sample titles. If ID-level resolution is needed later, it can be added without breaking changes.

## Decision 6: Frontend Query Builder Component

**Choice**: Composable `ContentQueryBuilder` component with live preview

```
web/src/components/query/
  ContentQueryBuilder.tsx    # Main component (composes sub-components)
  FilterChip.tsx             # Individual filter chip with remove button
  SourceFilter.tsx           # Multi-select source type filter
  StatusFilter.tsx           # Multi-select status filter
  DateRangeFilter.tsx        # Start/end date pickers with presets
  PublicationFilter.tsx      # Publication search/select
  QueryPreview.tsx           # Preview panel (count, breakdown, sample titles)
```

### Integration Points

1. **Summarize Dialog**: Add query builder with default `status: [pending, parsed]`, allowing source/date/publication filters. Button shows "Summarize N items" with count from preview.
2. **Generate Digest Dialog**: Add as collapsible "Advanced filters" section below existing date pickers. Default: no query (existing behavior). When expanded, shows query builder with preview.

### UX Flow

```
1. User opens "Summarize Content" dialog
2. Default filters shown: status = pending, parsed
3. User adds filter: source = youtube
4. Live preview updates: "23 items match" with source/status breakdown
5. User clicks "Preview" → sees list of matching titles (up to 10)
6. User clicks "Summarize 23 items" → batch operation starts
```

### Preview API Integration

```typescript
// web/src/hooks/useContentQuery.ts
export function useContentQueryPreview(query: ContentQuery) {
  return useQuery({
    queryKey: queryKeys.contents.queryPreview(query),
    queryFn: () => previewContentQuery(query),
    enabled: hasActiveFilters(query),
    staleTime: 2000,  // Debounce rapid filter changes
  });
}
```

**Error handling**: If preview API returns an error (network failure, 500), the QueryPreview component shows an error message with a "Retry" button. The previous preview state is retained until a successful response.

**Debouncing**: The 2-second staleTime means TanStack Query won't refetch within 2 seconds of the last successful response. For rapid typing, this effectively debounces. The preview API call itself is lightweight (COUNT + GROUP BY).

## Decision 7: Dry-Run Output Format

### CLI Output (Rich table)

```
$ aca summarize pending --source youtube,rss --after 2026-02-20 --dry-run

Content Query Preview
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Matching items: 23
  Date range: 2026-02-20 → 2026-02-25

  By Source:
    rss          8
    youtube     15

  By Status:
    parsed       5
    pending     18

  Sample Titles (showing 10 of 23):
    1. "GPT-5 Architecture Deep Dive" (youtube, 2026-02-24)
    2. "Weekly AI Roundup #47" (rss, 2026-02-23)
    3. "Anthropic Claude 4.5 Release Notes" (rss, 2026-02-22)
    ...

Run without --dry-run to summarize these 23 items.
```

**Breakdown ordering**: by_source and by_status are sorted alphabetically by key.

**Sample titles**: Up to 10 most recent titles (by published_date desc). When total_count > 10, shows "showing 10 of N".

### JSON Output (`--output json` combined with `--dry-run`)

```json
{
  "preview": {
    "total_count": 23,
    "by_source": {"rss": 8, "youtube": 15},
    "by_status": {"parsed": 5, "pending": 18},
    "date_range": {"earliest": "2026-02-20T08:30:00Z", "latest": "2026-02-25T14:15:00Z"},
    "sample_titles": ["GPT-5 Architecture Deep Dive", "Weekly AI Roundup #47", "..."]
  },
  "query": {
    "source_types": ["youtube", "rss"],
    "statuses": ["pending", "parsed"],
    "start_date": "2026-02-20T00:00:00Z"
  }
}
```

### Zero-match output

```
$ aca summarize pending --source youtube --after 2026-12-01 --dry-run

Content Query Preview
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Matching items: 0

No content matches the specified filters.
```
