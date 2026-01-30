## 2026-01-20 - Missing Timestamp Indexes
**Learning:** Core timestamp columns like `created_at` or `ingested_at` were missing database indexes despite being used frequently in `order_by` clauses for feed generation.
**Action:** Always verify indexes on columns used for sorting or filtering, especially in core content tables. Use `sqlalchemy.inspect` or check `__table__.indexes` in tests to prevent regression.

## 2026-01-26 - Summary Sort Optimization
**Learning:** The default sort order for the summary list endpoint is `created_at`, but the `Summary` table lacked an index on this column, leading to inefficient queries on large datasets.
**Action:** Added `index=True` to `Summary.created_at` and created a migration. Fixed a collision in Alembic revision history found during the process.
