## 2026-01-20 - Missing Timestamp Indexes
**Learning:** Core timestamp columns like `created_at` or `ingested_at` were missing database indexes despite being used frequently in `order_by` clauses for feed generation.
**Action:** Always verify indexes on columns used for sorting or filtering, especially in core content tables. Use `sqlalchemy.inspect` or check `__table__.indexes` in tests to prevent regression.

## 2026-01-20 - Subquery Performance
**Learning:** `NOT IN` subqueries (e.g., `~Content.id.in_(subquery)`) can be highly inefficient, especially on large datasets.
**Action:** Prefer `LEFT JOIN` ... `WHERE IS NULL` pattern for finding records without related records.

## 2026-01-26 - Missing Foreign Key Index on Self-Referential Relationship
**Learning:** The `canonical_id` self-referential foreign key in `Content` model was missing an index, causing potential performance issues during deduplication checks and deletion (cascading updates).
**Action:** Ensure all Foreign Keys, especially those used in filtering or joins (like self-referential ones), have `index=True` or an explicit index defined.

## 2026-02-04 - Inefficient `NOT IN` Set Lookup in Summarization Trigger
**Learning:** The summarization trigger was fetching ALL existing summary IDs into memory to filter out content that already has summaries. This scales poorly as the number of summaries grows.
**Action:** Replaced with a `LEFT JOIN` on `Summary` where `Summary.id IS NULL` to handle the filtering at the database level efficiently.

## 2026-02-09 - Deferring Heavy Columns in Bulk Operations
**Learning:** `Content` model has very large text/JSON columns (`markdown_content`, `tables_json`). When fetching bulk records for processing (e.g., triggering summarization), failure to `defer()` these columns can cause significant memory and time overhead, even if only IDs are needed.
**Action:** Always use `defer()` on heavy columns when fetching `Content` objects for background tasks or ID-only operations.

## 2026-02-15 - Explicit Column Selection for List Views
**Learning:** Even with `defer()`, `db.query(Content)` hydrates full ORM objects which adds significant overhead (~38% slower) compared to explicitly selecting only the required columns for list views.
**Action:** Prefer `db.query(Model.col1, Model.col2)` over `db.query(Model).options(defer(...))` when fetching data for list endpoints where only a subset of fields is needed.
